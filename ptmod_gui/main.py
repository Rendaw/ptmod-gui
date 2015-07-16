import argparse
import sys
import collections
import os.path
import pkg_resources

import polytaxis
from PyQt5.QtCore import (
    Qt, 
    QSize, 
    pyqtSignal,
    QItemSelection,
    QItemSelectionRange,
    QItemSelectionModel,
)
from PyQt5.QtGui import (
    QBrush, 
    QColor, 
    QCursor, 
    QIcon, 
    QPixmap,
)
from PyQt5.QtWidgets import (
    QSpinBox,
    QSizePolicy,
    QSplitter,
    QApplication,
    QFrame,
    QTreeWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QAbstractItemView,
    QTreeWidgetItem,
    QPushButton,
    QWidget,
    QMenu,
    QToolBar,
)


def res(path):
    return pkg_resources.resource_filename('ptmod_gui', 'data/' + path)


def yesno_dialog(window, main_layout, title):
    dialog = QDialog(window)
    dialog.setWindowTitle(title)

    layout = QVBoxLayout()

    layout.addLayout(main_layout)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, dialog)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    dialog.setLayout(layout)

    def yesno_dialog_inner(callback):
        dialog.accepted.connect(callback)
        dialog.exec_()
        return None
    return yesno_dialog_inner


class DropNotifyQTreeWidget(QTreeWidget):
    dropped = pyqtSignal()
    def dropEvent(self, event):
        super(DropNotifyQTreeWidget, self).dropEvent(event)
        self.dropped.emit()


class Icons:
    add = QIcon(res('ic_add_48px.svg'))
    remove = QIcon()
    undo = QIcon()
    menu = QIcon(res('ic_menu_48px.svg'))
    save = QIcon(res('ic_save_48px.svg'))
    close = QIcon(res('ic_close_48px.svg'))

    def __init__(self):
        self.remove.addFile(res('ic_remove_48px.svg'), QSize(), QIcon.Normal)
        self.remove.addFile(res('ic_remove_48px_fade.svg'), QSize(), QIcon.Disabled)
        self.undo.addFile(res('ic_undo_48px.svg'), QSize(), QIcon.Normal)
        self.undo.addFile(res('ic_undo_48px_fade.svg'), QSize(), QIcon.Disabled)


def os_path_split_asunder(path, windows):
    # Thanks http://stackoverflow.com/questions/4579908/cross-platform-splitting-of-path-in-python/4580931#4580931
    # Mod for windows paths on linux
    parts = []
    while True:
        newpath, tail = (ntpath.split if windows else os.path.split)(path)
        if newpath == path:
            assert not tail
            if path: parts.append(path)
            break
        parts.append(tail)
        path = newpath
    parts.reverse()
    return parts


def split_abs_path(path):
    windows = False
    out = []
    if len(path) > 1 and path[1] == ':':
        windows = True
        drive, path = ntpath.splitdrive(path)
        out.append(drive)
    extend = os_path_split_asunder(path, windows)
    if windows:
        extend.pop(0)
    out.extend(extend)
    return out


def cconnect(sig):
    def cconnect_inner(function):
        sig.connect(function)
        return function
    return cconnect_inner


def main():
    ## Setup
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(
        description='Edit polytaxis tags.',
    )
    parser.add_argument(
        'files',
        nargs='+',
        help='Tagged or untagged files to edit'
    )
    args = parser.parse_args()
    files = (
        (path, split_abs_path(path)[-1]) for path in 
            (os.path.abspath(filename) for filename in args.files)
    )

    targets = []
    selected_targets = set()
    ord_selected_targets = []
    shown_lines = []
    modified_lines = set()

    icons = Icons()

    ## Widgets
    # File list
    file_list = DropNotifyQTreeWidget()
    file_list.setSelectionMode(QTreeWidget.ExtendedSelection)
    file_list.setDragEnabled(True)
    file_list.setDragDropMode(QTreeWidget.InternalMove)
    file_list.viewport().setAcceptDrops(True)
    file_list.header().hide()
    file_list.setIndentation(0)

    # Tag table (editor)
    editor_tools = QToolBar()

    edit_add = editor_tools.addAction(icons.add, 'Add')
    edit_delete = editor_tools.addAction(icons.remove, 'Delete')
    edit_reset = editor_tools.addAction(icons.undo, 'Reset')
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    editor_tools.addWidget(spacer)
    edit_menu_menu = QMenu()
    edit_key = edit_menu_menu.addAction('Set key')
    edit_value = edit_menu_menu.addAction('Set value')
    edit_fill = edit_menu_menu.addAction('Fill')
    edit_focus = edit_menu_menu.addAction('Select Files')
    edit_number = edit_menu_menu.addAction('Generate numbers')
    #edit_multiline = edit_menu_menu.addAction('Input multiline')
    edit_menu = editor_tools.addAction(icons.menu, 'Menu')
    edit_menu.setMenu(edit_menu_menu)
    
    editor = QTreeWidget()
    editor.setSelectionMode(QTreeWidget.ExtendedSelection)
    editor.setHeaderLabels(['Tag', 'Value'])
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor.setIndentation(0)
    editor_layout = QVBoxLayout()
    editor_layout.addWidget(editor_tools)
    editor_layout.addWidget(editor)
    editor_layout.setSpacing(0)
    editor_layout.setContentsMargins(0, 0, 0, 0)
    editor_widget = QWidget()
    editor_widget.setLayout(editor_layout)
    
    # Main layout
    main_splitter = QSplitter(Qt.Horizontal)
    main_splitter.addWidget(file_list)
    main_splitter.addWidget(editor_widget)
    main_splitter.setStretchFactor(0, 1)
    main_splitter.setStretchFactor(1, 3)

    save = QPushButton(icons.save, 'Save')
    save.setEnabled(False)
    cancel = QPushButton(icons.close, 'Close')
    actions_layout = QHBoxLayout()
    actions_layout.addWidget(QWidget(), 1)
    actions_layout.addWidget(save)
    actions_layout.addWidget(cancel)

    window_layout = QVBoxLayout()
    window_layout.addWidget(main_splitter)
    window_layout.addLayout(actions_layout)

    window = QFrame()
    window.setLayout(window_layout)

    ## Logic
    def update_lines():
        selected_targets.clear()
        del ord_selected_targets[:]
        lines = set()
        def agg_row(item):
            target = targets[int(item.data(0, Qt.UserRole))]
            selected_targets.add(target)
            ord_selected_targets.append(target)
            for line in target.lines:
                lines.add(line)
        selected_rows = file_list.selectionModel().selectedRows()
        for row in selected_rows:
            item = file_list.invisibleRootItem().child(row.row())
            agg_row(item)
        if not selected_rows:
            for index in range(file_list.invisibleRootItem().childCount()):
                item = file_list.invisibleRootItem().child(index)
                agg_row(item)
        for line in shown_lines.copy():
            line.hide()
        del shown_lines[:]
        shown_lines.extend(
            sorted(
                list(lines), 
                key=lambda line: (line.original_key, line.original_val or '')
            )
        )
        for line in shown_lines:
            line.show()
        update_line_actions([])

    file_list.invisibleRootItem().setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled)
    @cconnect(file_list.itemSelectionChanged)
    def callback():
        update_lines()
    
    @cconnect(file_list.dropped)
    def callback():
        update_lines()

    @cconnect(edit_add.triggered)
    def callback(checked):
        Line(True, '', '', selected_targets)
        update_lines()

    @cconnect(editor.itemChanged)
    def callback(item, col):
        line = item.data(0, Qt.UserRole)
        line.update()

    editor_menu = QMenu()
    editor_menu_line = [None]
    val_fill = editor_menu.addAction('Fill')
    val_focus = editor_menu.addAction('Select Files')
    val_reset = editor_menu.addAction(icons.undo, 'Reset')
    val_delete = editor_menu.addAction(icons.remove, 'Delete')
    @cconnect(editor.customContextMenuRequested)
    def callback(point):
        item = editor.itemAt(point)
        if not item:
            return
        update_line_actions([item])
        editor_menu.popup(QCursor.pos())

    def update_line_actions(items):
        editor_menu_line[0] = [
            item.data(0, Qt.UserRole) for item in items
        ]
        actions = (
            val_fill,
            edit_fill,
            val_focus,
            edit_focus,
            val_reset,
            edit_reset,
            val_delete,
            edit_delete,
            edit_key,
            edit_value,
        )
        if items:
            for action in actions:
                action.setEnabled(True)
        else:
            for action in actions:
                action.setEnabled(False)
        line_targets = set()
        for line in editor_menu_line[0]:
            line_targets = line_targets.union(line.targets)
        for action in (val_fill, edit_fill):
            action.setText('Fill ({}/{})'.format(len(targets) - len(line_targets), len(targets)))
        for action in (val_focus, edit_focus):
            action.setText('Select Files ({})'.format(len(line_targets)))
        for action in (edit_number,):
            action.setText('Generate numbers ({})'.format(len(selected_targets)))
    
    editor_selection_model = editor.selectionModel()
    @cconnect(editor_selection_model.selectionChanged)
    def callback(selected, deselected):
        update_line_actions(editor.selectedItems())

    @cconnect(edit_fill.triggered)
    @cconnect(val_fill.triggered)
    def callback(checked):
        for line in editor_menu_line[0]:
            line.fill()
    
    @cconnect(edit_focus.triggered)
    @cconnect(val_focus.triggered)
    def callback(checked):
        targets = set()
        for line in editor_menu_line[0]:
            for target in line.targets:
                targets.add(target)
        selection = QItemSelection()
        for target in targets:
            selection.append(QItemSelectionRange(file_list.model().index(
                file_list.invisibleRootItem().indexOfChild(target.item),
                0,
            )))
        file_list.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect)
    
    @cconnect(edit_delete.triggered)
    @cconnect(val_delete.triggered)
    def callback(checked):
        for line in editor_menu_line[0]:
            line.delete()
    
    @cconnect(edit_reset.triggered)
    @cconnect(val_reset.triggered)
    def callback(checked):
        for line in editor_menu_line[0]:
            line.reset()
    
    @cconnect(edit_menu.triggered)
    def callback(checked):
        edit_menu_menu.exec_(QCursor.pos())
    
    @cconnect(edit_key.triggered)
    def callback(checked):
        layout = QGridLayout()
        layout.addWidget(QLabel('Key'), 0, 0)
        text = QLineEdit(editor_menu_line[0][0].key)
        layout.addWidget(text, 0, 1)
        @yesno_dialog(window, layout, 'Set keys ({})'.format(len(editor_menu_line[0])))
        def callback():
            for line in editor_menu_line[0]:
                line.item.setText(0, text.text())
                line.update()
    
    @cconnect(edit_value.triggered)
    def callback(checked):
        layout = QGridLayout()
        layout.addWidget(QLabel('Value'), 0, 0)
        text = QLineEdit(editor_menu_line[0][0].val)
        layout.addWidget(text, 0, 1)
        @yesno_dialog(window, layout, 'Set values ({})'.format(len(editor_menu_line[0])))
        def callback():
            for line in editor_menu_line[0]:
                line.item.setText(0, text.text())
                line.update()
    
    @cconnect(edit_number.triggered)
    def callback(checked):
        layout = QGridLayout()
        layout.addWidget(QLabel('Key'), 0, 0)
        key = QLineEdit('groupidx')
        layout.addWidget(key, 0, 1)
        layout.addWidget(QLabel('Start #'), 1, 0)
        start = QSpinBox()
        start.setValue(0)
        layout.addWidget(start, 1, 1)
        @yesno_dialog(window, layout, 'Generate numbers ({})'.format(len(ord_selected_targets)))
        def callback():
            for offset, target in enumerate(ord_selected_targets):
                Line(True, key.text(), str(start.value() + offset), {target})
            update_lines()
    
    @cconnect(save.clicked)
    def callback(checked):
        for target in targets:
            target.save()

    @cconnect(cancel.clicked)
    def callback(checked):
        app.exit()
    
    class Line:
        count = 0
        def __init__(self, new, key, val, targets):
            self.index = Line.count
            Line.count += 1
            self.new = new
            self.targets = targets.copy()
            self.original_targets = targets.copy()
            self.key = key
            self.original_key = key
            self.val = val
            self.original_val = val
            for target in targets:
                target.lines.add(self)

        def show(self):
            self.item = QTreeWidgetItem()
            self.item.setData(0, Qt.UserRole, self)
            self.item.setFlags(self.item.flags() | Qt.ItemIsEditable)
            self._refresh()
            editor.invisibleRootItem().addChild(self.item)

        def hide(self):
            if self.item is None:
                raise AssertionError('Line has no item')
            editor.invisibleRootItem().removeChild(self.item)
            self.item = None
            shown_lines.remove(self)

        def update(self):
            self.key = self.item.text(0)
            self.val = self.item.text(1)
            self._refresh()

        def _refresh(self):
            r = 0
            count = len(self.targets & selected_targets)
            total = len(selected_targets)
            a = 64 + (191 * count / total)
            deleted = False
            if count == 0:
                deleted = True
                a = 255
                r = 255
            b = 0
            if (
                    self.new or
                    self.key != self.original_key or
                    self.val != self.original_val or
                    self.targets != self.original_targets
                    ):
                if r != 255:
                    b = 255
                modified_lines.add(self)
                if len(modified_lines):
                    save.setEnabled(True)
            else:
                try:
                    modified_lines.remove(self)
                    if len(modified_lines) == 0:
                        save.setEnabled(False)
                except:
                    pass
            color = QBrush(QColor(r, 0, b, a))
            self.item.setForeground(0, color)
            self.item.setForeground(1, color)
            self.item.setText(0, self.key)
            self.item.setText(1, self.val)
            font = self.item.font(0)
            font.setStrikeOut(deleted)
            self.item.setFont(0, font)
            self.item.setFont(1, font)

        def fill(self):
            for target in targets:
                target.lines.add(self)
                self.targets.add(target)
            self._refresh()

        def reset(self):
            if self.new:
                for target in targets:
                    try:
                        target.lines.remove(self)
                    except:
                        pass
                self.hide()
                return
            for target in self.targets - self.original_targets:
                target.lines.remove(self)
            self.targets = self.original_targets.copy()
            self.key = self.original_key
            self.val = self.original_val
            self._refresh()

        def delete(self):
            self.targets -= selected_targets
            self._refresh()

        def save(self):
            self.original_targets = self.targets.copy()
            for target in targets:
                if target not in self.targets:
                    try:
                        target.lines.remove(self)
                    except:
                        pass
            self.new = False
            self.original_key = self.key
            self.original_val = self.val
            if len(self.targets & selected_targets) == 0:
                self.hide()
            else:
                self._refresh()

    all_tags = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: set()
        )
    )
    class Target:
        def __init__(self, path, filename, index):
            self.path = path
            self.filename = filename
            self.item = QTreeWidgetItem()
            self.item.setText(0, self.filename)
            self.item.setData(0, Qt.UserRole, index)
            self.item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            file_list.invisibleRootItem().addChild(self.item)

            tags = polytaxis.get_tags(path) or {}
            for key, vals in tags.items():
                for val in vals:
                    all_tags[key][val].add(self)

            self.lines = set()

        def save(self):
            tags = collections.defaultdict(lambda: set())
            for line in self.lines.copy():
                line.save()
            for line in self.lines:
                tags[line.key].add(line.val or None)
            self.path = polytaxis.set_tags(self.path, tags)
            self.filename = split_abs_path(self.path)[-1]
            self.item.setText(0, self.filename)
            self.set_title()
            modified_lines.clear()
            save.setEnabled(False)

        def set_title(self):
            new_title = 'ptmod: {}'.format(', '.join(target.filename for target in targets))
            if window.windowTitle() != new_title:
                window.setWindowTitle(new_title)

    for index, (path, filename) in enumerate(files):
        targets.append(Target(path, filename, index))

    for key, vals in all_tags.items():
        for val, line_targets in vals.items():
            Line(False, key, val, line_targets)

    update_lines()

    first_target = next(iter(targets), None)
    if first_target:
        first_target.set_title()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
