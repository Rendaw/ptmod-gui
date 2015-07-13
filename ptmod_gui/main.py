import argparse
import sys
import collections

import polytaxis
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QCursor
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QTreeWidget,
    QHBoxLayout,
    QVBoxLayout,
    QAbstractItemView,
    QTreeWidgetItem,
    QPushButton,
    QWidget,
    QMenu,
    QToolBar,
)

def cconnect(sig):
    def cconnect_inner(function):
        sig.connect(function)
        return function
    return cconnect_inner

def main():
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

    targets = []
    selected_targets = []
    shown_lines = []

    file_list = QTreeWidget()
    file_list.setSelectionMode(QTreeWidget.ExtendedSelection)
    file_list.setDragEnabled(True)
    file_list.setDragDropMode(QTreeWidget.InternalMove)
    file_list.viewport().setAcceptDrops(True)
    file_list.header().hide()
    editor_tools = QToolBar()
    edit_add = editor_tools.addAction('Add')
    edit_reset = editor_tools.addAction('Reset')
    edit_delete = editor_tools.addAction('Delete')
    editor = QTreeWidget()
    #editor.setColumnCount(2)
    editor.setHeaderLabels(['Tag', 'Value'])
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor_layout = QVBoxLayout()
    editor_layout.addWidget(editor_tools)
    editor_layout.addWidget(editor)
    
    main_layout = QHBoxLayout()
    main_layout.addWidget(file_list)
    main_layout.addLayout(editor_layout)

    save = QPushButton('Save')
    reset = QPushButton('Reset')
    cancel = QPushButton('Cancel')
    actions_layout = QHBoxLayout()
    actions_layout.addWidget(QWidget(), 1)
    actions_layout.addWidget(save)
    actions_layout.addWidget(cancel)

    window_layout = QVBoxLayout()
    window_layout.addLayout(main_layout)
    window_layout.addLayout(actions_layout)

    window = QFrame()
    window.setLayout(window_layout)

    def update_selection():
        lines = set()
        def agg_row(item):
            target = targets[int(item.data(0, Qt.UserRole))]
            for line in target.lines:
                lines.add(line)
        selected_rows = file_list.selectionModel().selectedRows()
        for row in selected_rows:
            item = file_list.invisibleRootItem().child(row.row())
            agg_row(item)
        if not selected_rows:
            for target in targets:
                agg_row(target.item)
        for line in shown_lines:
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

    file_list.invisibleRootItem().setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled)
    file_list_selection_model = file_list.selectionModel()
    @cconnect(file_list_selection_model.selectionChanged)
    def callback(selected, deselected):
        update_selection()

    @cconnect(edit_add.triggered)
    def callback(checked):
        Line(True, '', '', selected_targets)

    @cconnect(editor.itemChanged)
    def callback(item, col):
        line = item.data(0, Qt.UserRole)
        line.update()

    editor_menu = QMenu()
    editor_menu_line = [None]
    val_fill = editor_menu.addAction('Fill')
    val_focus = editor_menu.addAction('Select Files')
    val_reset = editor_menu.addAction('Reset')
    val_delete = editor_menu.addAction('Delete')
    @cconnect(editor.customContextMenuRequested)
    def callback(point):
        item = editor.itemAt(point)
        if not item:
            return
        update_line_actions(True)
        line = item.data(0, Qt.UserRole)
        val_fill.setText('Fill ({}/{})'.format(len(targets) - len(line.targets), len(targets)))
        val_focus.setText('Select Files ({})'.format(len(line.targets)))
        editor_menu_line[0] = line
        editor_menu.popup(QCursor.pos())

    def update_line_actions(on):
        actions = (
            val_fill,
            val_focus,
            val_reset,
            edit_reset,
            val_delete,
            edit_delete,
        )
        if on:
            for action in actions:
                action.setEnabled(True)
        else:
            for action in actions:
                action.setEnabled(False)
    
    editor_selection_model = editor.selectionModel()
    @cconnect(editor_selection_model.selectionChanged)
    def callback(selected, deselected):
        selected_rows = file_list.selectionModel().selectedRows()
        update_line_actions(selected_rows)

    @cconnect(val_fill.triggered)
    def callback(checked):
        editor_menu_line[0].fill()
    
    @cconnect(val_focus.triggered)
    def callback(checked):
        for target in editor_menu_line[0].targets:
            pass  # TODO
    
    @cconnect(edit_reset.triggered)
    @cconnect(val_reset.triggered)
    def callback(checked):
        editor_menu_line[0].reset()
    
    @cconnect(edit_delete.triggered)
    @cconnect(val_delete.triggered)
    def callback(checked):
        editor_menu_line[0].delete()
    
    @cconnect(save.clicked)
    def callback(checked):
        # TODO
        pass

    @cconnect(reset.clicked)
    def callback(checked):
        for line in shown_lines:
            line.reset()

    @cconnect(cancel.clicked)
    def callback(checked):
        app.exit()
    
    class Line:
        count = 0
        def __init__(self, new, key, val, targets):
            self.index = Line.count
            Line.count += 1
            self.new = new
            self.targets = targets
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

        def update(self):
            self.key = self.item.text(0)
            self.val = self.item.text(1)

        def _refresh(self):
            if len(self.targets) == 0:
                color = QBrush(QColor(255, 0, 0, 255))
            else:
                color = QBrush(QColor(0, 0, 0, len(self.targets) * 255 / len(targets)))
            self.item.setForeground(0, color)
            self.item.setForeground(1, color)
            self.item.setText(0, self.key)
            self.item.setText(1, self.val)

        def fill(self):
            for target in targets:
                target.lines.add(self)
                self.targets.add(target)
            self._refresh()

        def reset(self):
            if self.new:
                for target in targets:
                    target.lines.remove(self)
                self.hide()
                return
            for target in self.targets - self.original_targets:
                target.lines.remove(self)
            self.targets = self.original_targets.copy()
            self.key = self.original_key
            self.val = self.original_val
            self._refresh()

        def delete(self):
            self.targets = set()
            self._refresh()

        def save(self):
            self.original_targets = self.targets.copy()
            if len(self.targets) == 0:
                self.hide()
                return
            self.new = False
            self.original_key = self.key
            self.original_val = self.val

    all_tags = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: set()
        )
    )
    class Target:
        def __init__(self, filename, index):
            self.filename = filename
            self.item = QTreeWidgetItem()
            self.item.setText(0, self.filename)
            self.item.setData(0, Qt.UserRole, index)
            self.item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
            file_list.invisibleRootItem().addChild(self.item)

            tags = polytaxis.get_tags(filename) or {}
            for key, vals in tags.items():
                for val in vals:
                    all_tags[key][val].add(self)

            self.lines = set()

        def save(self):
            # TODO
            pass

    for index, filename in enumerate(args.files):
        targets.append(Target(filename, index))

    for key, vals in all_tags.items():
        for val, line_targets in vals.items():
            Line(False, key, val, line_targets)

    update_selection()

    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
