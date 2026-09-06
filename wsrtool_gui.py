# wsrtool_gui.py
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QGroupBox, QFileDialog, QMessageBox,
    QTabWidget, QTextEdit, QPushButton, QStatusBar, QToolBar,
    QTableWidget, QTableWidgetItem, QComboBox, QDialog, QHeaderView,
    QListWidget, QLineEdit, QCheckBox, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QBrush

try:
    from fw_core import Firmware, TYPE_LABEL, display_raw_mid, display_speed
except ImportError:
    print("错误: 找不到 fw_core.py")
    sys.exit(1)


def get_record_color(record):
    record_type = record['type']
    colors = {
        'valid': QColor(230, 255, 230),
        'reserved': QColor(255, 255, 200),
        'empty': QColor(240, 240, 240),
        'zero': QColor(255, 220, 200),
        'invalid': QColor(255, 200, 200),
    }
    return colors.get(record_type, QColor(255, 255, 255))


def format_candidates(candidates):
    if not candidates:
        return "未知"
    if len(candidates) == 1:
        c = candidates[0]
        return f"{c['media_type']} / {c['recording']} / {c['nominal_speed']}"
    types = set(c['media_type'] for c in candidates)
    return f"有歧义 ({len(candidates)} 个候选: {', '.join(types)})"


class RecordDetailDialog(QDialog):
    def __init__(self, parent, table_name, record):
        super().__init__(parent)
        self.table_name = table_name
        self.record = record
        self.setWindowTitle(f"记录详情 - {table_name}[{record['idx']}]")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        info = QTextEdit()
        info.setReadOnly(True)
        r = self.record
        lines = []
        lines.append(f"物理表: {self.table_name}")
        lines.append(f"槽位索引: {r['idx']}")
        lines.append(f"明文偏移: 0x{r['off']:05X}")
        lines.append(f"记录类型: {TYPE_LABEL[r['type']]}")
        lines.append("")
        
        if r['type'] == 'valid':
            lines.append(f"MID: {r['mid']}")
            lines.append(f"MID 原始字节: {r['mid_raw'].hex()}")
            lines.append("")
            lines.append(f"参数 ({len(r['params'])} 字节):")
            lines.append(f"  {r['params'].hex()}")
            lines.append("")
            if len(r['params']) >= 2:
                speed_byte = r['params'][1]
                lines.append(f"速度位图 (字节 1): 0x{speed_byte:02X}")
                lines.append(f"速度: {display_speed(speed_byte)}")
                lines.append("")
            lines.append("Excel 参考:")
            if not r['candidates']:
                lines.append("  (无匹配)")
            elif len(r['candidates']) == 1:
                c = r['candidates'][0]
                lines.append(f"  显示名: {c['display']}")
                lines.append(f"  介质类型: {c['media_type']}")
                lines.append(f"  容量: {c['capacity']}")
                lines.append(f"  层数: {c['layers']}")
                lines.append(f"  记录类型: {c['recording']}")
                lines.append(f"  标称速度: {c['nominal_speed']}")
            else:
                lines.append(f"  有 {len(r['candidates'])} 个候选:")
                for i, c in enumerate(r['candidates'], 1):
                    lines.append(f"    {i}. {c['media_type']} / {c['recording']} / {c['nominal_speed']}")
        elif r['type'] == 'reserved':
            lines.append("MID 字段: 全 FF")
            lines.append(f"参数 ({len(r['params'])} 字节):")
            lines.append(f"  {r['params'].hex()}")
        elif r['type'] == 'empty':
            lines.append(f"整条记录: 全 FF ({len(r['mid_raw']) + len(r['params'])} 字节)")
        elif r['type'] == 'zero':
            lines.append(f"整条记录: 全 00 ({len(r['mid_raw']) + len(r['params'])} 字节)")
        elif r['type'] == 'invalid':
            lines.append("MID 字段包含非 ASCII 字符:")
            lines.append(f"  {r['mid_raw'].hex()}")
            lines.append(f"  显示: {display_raw_mid(r['mid_raw'])}")
        
        info.setPlainText("\n".join(lines))
        layout.addWidget(info)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)




class RecordEditDialog(QDialog):
    def __init__(self, parent, fw, table_name, record):
        super().__init__(parent)
        self.fw = fw
        self.table_name = table_name
        self.record = record
        self.setWindowTitle(f"编辑记录 - {table_name}[{record['idx']}]")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        info_label = QLabel(f"物理表: {self.table_name}[{self.record['idx']}] | "
                           f"偏移: 0x{self.record['off']:05X} | "
                           f"类型: {TYPE_LABEL[self.record['type']]}")
        layout.addWidget(info_label)
        
        mid_group = QGroupBox("MID (前缀 + 后缀)")
        mid_layout = QFormLayout()
        
        # 解析当前 MID
        if self.record['type'] == 'valid':
            mid_raw = self.record['mid_raw']
            # 前 6 字节是前缀，后 3 字节是后缀
            prefix_bytes = mid_raw[:6]
            suffix_bytes = mid_raw[6:9]
            
            # 去掉尾部 \x00
            prefix = prefix_bytes.rstrip(b'\x00').decode('ascii', 'ignore')
            suffix = suffix_bytes.rstrip(b'\x00').decode('ascii', 'ignore')
        else:
            prefix = ''
            suffix = ''
        
        self.prefix_input = QLineEdit()
        self.prefix_input.setMaxLength(6)
        self.prefix_input.setPlaceholderText("厂商名，最多 6 字符")
        self.prefix_input.setText(prefix)
        mid_layout.addRow("前缀:", self.prefix_input)
        
        self.suffix_input = QLineEdit()
        self.suffix_input.setMaxLength(3)
        self.suffix_input.setPlaceholderText("型号，最多 3 字符")
        self.suffix_input.setText(suffix)
        mid_layout.addRow("后缀:", self.suffix_input)
        
        mid_hint = QLabel("示例: 前缀=SONY 后缀=NQ1 → SONY□□NQ1 (□ 是 \\x00)")
        mid_hint.setStyleSheet("color: gray; font-size: 10px;")
        mid_layout.addRow("", mid_hint)
        
        mid_group.setLayout(mid_layout)
        layout.addWidget(mid_group)
        
        form_layout = QFormLayout()
        
        self.params_input = QLineEdit()
        param_len = len(self.record['params'])
        self.params_input.setPlaceholderText(f"十六进制，{param_len * 2} 个字符 ({param_len} 字节)")
        self.params_input.setText(self.record['params'].hex())
        form_layout.addRow("参数 (Hex):", self.params_input)
        
        layout.addLayout(form_layout)
        
        if len(self.record['params']) >= 2:
            speed_group = QGroupBox("速度位图 (字节 1)")
            speed_layout = QHBoxLayout()
            
            self.speed_checks = {}
            speed_bits = [
                (0x02, '2x'),
                (0x04, '4x'),
                (0x08, '6x'),
                (0x10, '8x'),
                (0x20, '10x'),
                (0x40, '12x'),
                (0x80, '16x'),
            ]
            
            current_speed = self.record['params'][1]
            for bit, name in speed_bits:
                cb = QCheckBox(name)
                cb.setChecked(bool(current_speed & bit))
                cb.stateChanged.connect(self.on_speed_changed)
                self.speed_checks[bit] = cb
                speed_layout.addWidget(cb)
            
            speed_group.setLayout(speed_layout)
            layout.addWidget(speed_group)
        else:
            self.speed_checks = {}
        
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("注意:"))
        layout.addWidget(QLabel("• MID 前缀+后缀只能包含 ASCII 字母、数字和符号"))
        layout.addWidget(QLabel("• 前缀最多 6 字符，后缀最多 3 字符"))
        layout.addWidget(QLabel("• 参数必须是偶数个十六进制字符 (0-9, A-F)"))
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_changes)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def on_speed_changed(self):
        speed_byte = 0
        for bit, cb in self.speed_checks.items():
            if cb.isChecked():
                speed_byte |= bit
        
        params_hex = self.params_input.text()
        if len(params_hex) >= 2:
            try:
                params_bytes = bytearray.fromhex(params_hex)
                if len(params_bytes) >= 2:
                    params_bytes[1] = speed_byte
                    self.params_input.setText(params_bytes.hex())
            except:
                pass
    
    def save_changes(self):
        prefix = self.prefix_input.text().strip()
        suffix = self.suffix_input.text().strip()
        params_hex = self.params_input.text().strip()
        
        if not prefix:
            QMessageBox.warning(self, "输入错误", "MID 前缀不能为空")
            return
        
        if len(prefix) > 6:
            QMessageBox.warning(self, "输入错误", "MID 前缀最多 6 个字符")
            return
        
        if len(suffix) > 3:
            QMessageBox.warning(self, "输入错误", "MID 后缀最多 3 个字符")
            return
        
        try:
            prefix.encode('ascii')
            suffix.encode('ascii')
        except:
            QMessageBox.warning(self, "输入错误", "MID 前缀和后缀只能包含 ASCII 字符")
            return
        
        # 构造 9 字节 MID
        prefix_bytes = prefix.encode('ascii').ljust(6, b'\x00')
        suffix_bytes = suffix.encode('ascii').ljust(3, b'\x00')
        mid_bytes = prefix_bytes + suffix_bytes
        mid_str = mid_bytes.rstrip(b'\x00').decode('ascii', 'ignore')
        
        if not all(c in '0123456789ABCDEFabcdef' for c in params_hex):
            QMessageBox.warning(self, "输入错误", "参数必须是十六进制字符 (0-9, A-F)")
            return
        
        if len(params_hex) % 2 != 0:
            QMessageBox.warning(self, "输入错误", "参数必须是偶数个字符")
            return
        
        try:
            params_bytes = bytes.fromhex(params_hex)
        except:
            QMessageBox.warning(self, "输入错误", "参数十六进制格式错误")
            return
        
        expected_len = len(self.record['params'])
        if len(params_bytes) != expected_len:
            QMessageBox.warning(
                self, "输入错误",
                f"参数长度错误：需要 {expected_len} 字节，实际 {len(params_bytes)} 字节"
            )
            return
        
        try:
            self.fw.set_record(
                self.table_name,
                self.record['idx'],
                mid=mid_str,
                params=params_bytes
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存记录:\n{str(e)}")




class RecordAddDialog(QDialog):
    def __init__(self, parent, fw, default_table='BD-XL'):
        super().__init__(parent)
        self.fw = fw
        self.setWindowTitle("新增记录")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.default_table = default_table
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.table_selector = QComboBox()
        self.table_selector.addItems(['BD-XL', '15B-A', '15B-B', '15B-C', '15B-D'])
        self.table_selector.setCurrentText(self.default_table)
        self.table_selector.currentTextChanged.connect(self.on_table_changed)
        form_layout.addRow("目标物理表:", self.table_selector)
        
        self.slot_selector = QComboBox()
        form_layout.addRow("插入槽位:", self.slot_selector)
        
        layout.addLayout(form_layout)
        
        self.slot_info_label = QLabel()
        layout.addWidget(self.slot_info_label)
        
        mid_group = QGroupBox("MID (前缀 + 后缀)")
        mid_layout = QFormLayout()
        
        self.prefix_input = QLineEdit()
        self.prefix_input.setMaxLength(6)
        self.prefix_input.setPlaceholderText("厂商名，最多 6 字符")
        mid_layout.addRow("前缀:", self.prefix_input)
        
        self.suffix_input = QLineEdit()
        self.suffix_input.setMaxLength(3)
        self.suffix_input.setPlaceholderText("型号，最多 3 字符，可为空")
        mid_layout.addRow("后缀:", self.suffix_input)
        
        mid_hint = QLabel("示例: 前缀=SONY 后缀=NQ1 → SONY□□NQ1 (□ 是 \\x00)")
        mid_hint.setStyleSheet("color: gray; font-size: 10px;")
        mid_layout.addRow("", mid_hint)
        
        mid_group.setLayout(mid_layout)
        layout.addWidget(mid_group)
        
        form_layout2 = QFormLayout()
        
        self.params_input = QLineEdit()
        self.params_input.setPlaceholderText("十六进制")
        form_layout2.addRow("参数 (Hex):", self.params_input)
        
        layout.addLayout(form_layout2)
        
        speed_group = QGroupBox("速度位图 (参数字节 1，仅 BD-XL 有效)")
        speed_layout = QHBoxLayout()
        
        self.speed_checks = {}
        speed_bits = [
            (0x02, '2x'),
            (0x04, '4x'),
            (0x08, '6x'),
            (0x10, '8x'),
            (0x20, '10x'),
            (0x40, '12x'),
            (0x80, '16x'),
        ]
        
        for bit, name in speed_bits:
            cb = QCheckBox(name)
            cb.stateChanged.connect(self.on_speed_changed)
            self.speed_checks[bit] = cb
            speed_layout.addWidget(cb)
        
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("注意:"))
        layout.addWidget(QLabel("• MID 前缀必填，后缀可选"))
        layout.addWidget(QLabel("• 前缀最多 6 字符，后缀最多 3 字符"))
        layout.addWidget(QLabel("• 前缀+后缀总长度不足 9 字节时，自动用 \\x00 补齐"))
        layout.addWidget(QLabel("• 参数长度：BD-XL = 12 字节，15B 表 = 6 字节"))
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        add_btn = QPushButton("新增")
        add_btn.clicked.connect(self.add_record)
        btn_layout.addWidget(add_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.on_table_changed(self.default_table)
    
    def on_table_changed(self, table_name):
        self.slot_selector.clear()
        
        try:
            table_data = self.fw.table(table_name)
        except:
            return
        
        empty_slots = [r for r in table_data['records'] if r['type'] == 'empty']
        
        if not empty_slots:
            self.slot_selector.addItem("(无可用空槽)")
            self.slot_info_label.setText(f"{table_name} 没有空闲槽位，无法新增")
            return
        
        self.slot_selector.addItem(f"自动选择 (第一个空槽: [{empty_slots[0]['idx']}])")
        
        for slot in empty_slots:
            self.slot_selector.addItem(f"槽位 [{slot['idx']}] @0x{slot['off']:05X}")
        
        param_len = table_data['stride'] - 9
        self.slot_info_label.setText(
            f"{table_name}: {len(empty_slots)} 个空槽可用 | "
            f"参数长度: {param_len} 字节 ({param_len * 2} 个十六进制字符)"
        )
        
        default_params = '00' * param_len
        if self.params_input.text() == '' or len(self.params_input.text()) != param_len * 2:
            self.params_input.setText(default_params)
    
    def on_speed_changed(self):
        speed_byte = 0
        for bit, cb in self.speed_checks.items():
            if cb.isChecked():
                speed_byte |= bit
        
        params_hex = self.params_input.text()
        if len(params_hex) >= 2:
            try:
                params_bytes = bytearray.fromhex(params_hex)
                if len(params_bytes) >= 2:
                    params_bytes[1] = speed_byte
                    self.params_input.setText(params_bytes.hex())
            except:
                pass
    
    def add_record(self):
        table_name = self.table_selector.currentText()
        slot_text = self.slot_selector.currentText()
        prefix = self.prefix_input.text().strip()
        suffix = self.suffix_input.text().strip()
        params_hex = self.params_input.text().strip()
        
        if slot_text.startswith("(无可用空槽)"):
            QMessageBox.warning(self, "无法新增", f"{table_name} 没有空闲槽位")
            return
        
        if not prefix:
            QMessageBox.warning(self, "输入错误", "MID 前缀不能为空")
            return
        
        if len(prefix) > 6:
            QMessageBox.warning(self, "输入错误", "MID 前缀最多 6 个字符")
            return
        
        if len(suffix) > 3:
            QMessageBox.warning(self, "输入错误", "MID 后缀最多 3 个字符")
            return
        
        try:
            prefix.encode('ascii')
            suffix.encode('ascii')
        except:
            QMessageBox.warning(self, "输入错误", "MID 前缀和后缀只能包含 ASCII 字符")
            return
        
        # 构造 9 字节 MID
        prefix_bytes = prefix.encode('ascii').ljust(6, b'\x00')
        suffix_bytes = suffix.encode('ascii').ljust(3, b'\x00')
        mid_bytes = prefix_bytes + suffix_bytes
        mid_str = mid_bytes.rstrip(b'\x00').decode('ascii', 'ignore')
        
        if not all(c in '0123456789ABCDEFabcdef' for c in params_hex):
            QMessageBox.warning(self, "输入错误", "参数必须是十六进制字符 (0-9, A-F)")
            return
        
        if len(params_hex) % 2 != 0:
            QMessageBox.warning(self, "输入错误", "参数必须是偶数个字符")
            return
        
        try:
            params_bytes = bytes.fromhex(params_hex)
        except:
            QMessageBox.warning(self, "输入错误", "参数十六进制格式错误")
            return
        
        expected_len = self.fw.table(table_name)['stride'] - 9
        if len(params_bytes) != expected_len:
            QMessageBox.warning(
                self, "输入错误",
                f"参数长度错误：{table_name} 需要 {expected_len} 字节，实际 {len(params_bytes)} 字节"
            )
            return
        
        slot_idx = None
        if not slot_text.startswith("自动选择"):
            try:
                slot_idx = int(slot_text.split('[')[1].split(']')[0])
            except:
                pass
        
        try:
            added_idx = self.fw.add_record(table_name, mid_str, params_bytes, slot=slot_idx)
            QMessageBox.information(
                self, "新增成功",
                f"已在 {table_name}[{added_idx}] 新增记录\n前缀: {prefix}\n后缀: {suffix}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "新增失败", f"无法新增记录:\n{str(e)}")




class CopyRecordDialog(QDialog):
    """复制记录对话框"""
    
    def __init__(self, parent, fw, src_table, src_record):
        super().__init__(parent)
        self.fw = fw
        self.src_table = src_table
        self.src_record = src_record
        
        self.setWindowTitle(f"复制记录 - {src_table}[{src_record['idx']}]")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 源记录信息
        src_group = QGroupBox("源记录")
        src_layout = QVBoxLayout()
        
        src_info = []
        src_info.append(f"物理表: {self.src_table}")
        src_info.append(f"槽位索引: {self.src_record['idx']}")
        
        if self.src_record['type'] == 'valid':
            src_info.append(f"MID: {self.src_record['mid']}")
        else:
            src_info.append(f"类型: {TYPE_LABEL[self.src_record['type']]}")
        
        src_info.append(f"参数: {self.src_record['params'].hex()}")
        
        src_label = QLabel('\n'.join(src_info))
        src_layout.addWidget(src_label)
        src_group.setLayout(src_layout)
        layout.addWidget(src_group)
        
        # 目标选择
        dst_group = QGroupBox("目标位置")
        dst_layout = QVBoxLayout()
        
        # 表选择
        table_layout = QHBoxLayout()
        table_layout.addWidget(QLabel("目标表:"))
        self.table_combo = QComboBox()
        self.table_combo.addItems(['BD-XL', '15B-A', '15B-B', '15B-C', '15B-D'])
        self.table_combo.currentTextChanged.connect(self.on_table_changed)
        table_layout.addWidget(self.table_combo)
        table_layout.addStretch()
        dst_layout.addLayout(table_layout)
        
        # 槽位选择
        slot_layout = QHBoxLayout()
        slot_layout.addWidget(QLabel("目标槽位:"))
        self.slot_combo = QComboBox()
        slot_layout.addWidget(self.slot_combo)
        slot_layout.addStretch()
        dst_layout.addLayout(slot_layout)
        
        # 警告标签
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color: red;")
        self.warning_label.setWordWrap(True)
        dst_layout.addWidget(self.warning_label)
        
        dst_group.setLayout(dst_layout)
        layout.addWidget(dst_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.copy_btn = QPushButton("确定复制")
        self.copy_btn.clicked.connect(self.do_copy)
        btn_layout.addWidget(self.copy_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # 初始化
        self.on_table_changed(self.table_combo.currentText())
    
    def on_table_changed(self, table_name):
        """目标表改变时更新槽位列表"""
        self.slot_combo.clear()
        self.warning_label.setText("")
        
        try:
            table_data = self.fw.table(table_name)
            records = table_data['records']
            
            for i, rec in enumerate(records):
                label = f"[{i}] {TYPE_LABEL[rec['type']]}"
                if rec['type'] == 'valid':
                    label += f" - {rec['mid']}"
                elif rec['type'] == 'reserved':
                    label += f" - {rec['params'].hex()[:16]}..."
                
                self.slot_combo.addItem(label, i)
            
            # 检查步长兼容性
            src_stride = self.fw.table(self.src_table)['stride']
            dst_stride = table_data['stride']
            
            if src_stride != dst_stride:
                if src_stride > dst_stride:
                    self.warning_label.setText(
                        f"⚠ 警告: 源记录 {src_stride} 字节，目标表 {dst_stride} 字节，参数将被截断"
                    )
                else:
                    self.warning_label.setText(
                        f"ℹ 提示: 源记录 {src_stride} 字节，目标表 {dst_stride} 字节，将用 0xFF 补齐"
                    )
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载目标表:\n{str(e)}")
    
    def do_copy(self):
        """执行复制"""
        dst_table = self.table_combo.currentText()
        dst_slot = self.slot_combo.currentData()
        
        if dst_slot is None:
            QMessageBox.warning(self, "错误", "请选择目标槽位")
            return
        
        try:
            # 调用 fw_core 的 copy_record 方法
            self.fw.copy_record(
                self.src_table,
                self.src_record['idx'],
                dst_table,
                dst_slot
            )
            
            QMessageBox.information(
                self,
                "复制成功",
                f"已将 {self.src_table}[{self.src_record['idx']}] 复制到 {dst_table}[{dst_slot}]"
            )
            
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "复制失败", f"无法复制记录:\n{str(e)}")


class PhysicalTableView(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.current_table = 'BD-XL'
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("选择物理表:"))
        self.table_selector = QComboBox()
        self.table_selector.addItems(['BD-XL', '15B-A', '15B-B', '15B-C', '15B-D'])
        self.table_selector.currentTextChanged.connect(self.on_table_changed)
        top_layout.addWidget(self.table_selector)
        self.table_info_label = QLabel()
        top_layout.addWidget(self.table_info_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(7)
        self.table_widget.setHorizontalHeaderLabels([
            '序号', '状态', 'MID', '介质类型', '参数', '速度', '物理位置'
        ])
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("新增记录")
        self.add_btn.clicked.connect(self.add_record)
        btn_layout.addWidget(self.add_btn)
        self.edit_btn = QPushButton("编辑选中记录")
        self.edit_btn.clicked.connect(self.edit_selected)
        btn_layout.addWidget(self.edit_btn)
        self.detail_btn = QPushButton("查看详情")
        self.detail_btn.clicked.connect(self.show_selected_detail)
        self.delete_btn = QPushButton("删除选中记录")
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.delete_btn)
        self.copy_btn = QPushButton("复制到...")
        self.copy_btn.clicked.connect(self.copy_selected)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.detail_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_table(self, fw, table_name):
        if not fw:
            self.table_widget.setRowCount(0)
            self.table_info_label.setText("")
            return
        self.current_table = table_name
        try:
            table_data = fw.table(table_name)
        except ValueError:
            self.table_widget.setRowCount(0)
            self.table_info_label.setText("无效的表名")
            return
        records = table_data['records']
        counts = {}
        for r in records:
            counts[r['type']] = counts.get(r['type'], 0) + 1
        count_text = ' | '.join(f"{TYPE_LABEL[k]}={counts[k]}" for k in sorted(counts.keys()))
        info_text = (f"明文范围 0x{table_data['start']:05X}-0x{table_data['end']:05X} | "
                    f"步长 {table_data['stride']} | 容量 {table_data['capacity']} | {count_text}")
        self.table_info_label.setText(info_text)
        self.table_widget.setRowCount(len(records))

        for row, record in enumerate(records):
            idx_item = QTableWidgetItem(str(record['idx']))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_widget.setItem(row, 0, idx_item)

            status_item = QTableWidgetItem(TYPE_LABEL[record['type']])
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_widget.setItem(row, 1, status_item)

            if record['type'] == 'valid':
                mid_text = record['mid']
                if record['deleted']:
                    mid_text += " [已删除]"
            else:
                mid_text = display_raw_mid(record['mid_raw'])
            mid_item = QTableWidgetItem(mid_text)
            self.table_widget.setItem(row, 2, mid_item)

            media_item = QTableWidgetItem(format_candidates(record['candidates']))
            self.table_widget.setItem(row, 3, media_item)

            params_item = QTableWidgetItem(record['params'].hex())
            self.table_widget.setItem(row, 4, params_item)

            if record['type'] == 'valid' and len(record['params']) >= 2:
                speed_byte = record['params'][1]
                speed_text = f"0x{speed_byte:02X} {display_speed(speed_byte)}"
            else:
                speed_text = "-"
            speed_item = QTableWidgetItem(speed_text)
            self.table_widget.setItem(row, 5, speed_item)

            location_item = QTableWidgetItem(f"{table_name}[{record['idx']}] @0x{record['off']:05X}")
            self.table_widget.setItem(row, 6, location_item)

            color = get_record_color(record)
            text_color = QColor(0, 0, 0)
            for col in range(7):
                item = self.table_widget.item(row, col)
                if item:
                    item.setBackground(QBrush(color))
                    item.setForeground(QBrush(text_color))

    def on_table_changed(self, table_name):
        fw = self.parent_window.fw
        if fw:
            self.load_table(fw, table_name)

    def current_record(self):
        fw = self.parent_window.fw
        if not fw:
            return None
        row = self.table_widget.currentRow()
        if row < 0:
            return None
        records = fw.table(self.current_table)['records']
        if row >= len(records):
            return None
        return records[row]

    def on_row_double_clicked(self, index):
        self.edit_selected()

    def show_selected_detail(self):
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        dialog = RecordDetailDialog(self, self.current_table, record)
        dialog.exec()

    def add_record(self):
        fw = self.parent_window.fw
        if not fw:
            return

        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return

        dialog = RecordAddDialog(self, fw, default_table=self.current_table)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()

    def edit_selected(self):
        fw = self.parent_window.fw
        if not fw:
            return
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return

        if record['type'] in ('zero', 'invalid'):
            QMessageBox.warning(
                self, "不允许编辑",
                f"{self.current_table}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许编辑"
            )
            return

        if record['type'] == 'empty':
            QMessageBox.information(
                self, "提示",
                f"{self.current_table}[{record['idx']}] 是全 FF 空槽，请使用「新增记录」功能"
            )
            return

        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return

        dialog = RecordEditDialog(self, fw, self.current_table, record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()


    def delete_selected(self):
        fw = self.parent_window.fw
        if not fw:
            return
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        if record['type'] not in ('valid', 'reserved'):
            QMessageBox.warning(
                self, "不允许删除",
                f"{self.current_table}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许删除"
            )
            return
        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return
        mid_display = record['mid'] if record['type'] == 'valid' else '[保留槽位]'
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除以下记录吗？\n\n"
            f"物理表: {self.current_table}[{record['idx']}]\n"
            f"MID: {mid_display}\n"
            f"偏移: 0x{record['off']:05X}\n\n"
            f"删除后该槽位将变为全 FF 空槽。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            fw.delete_record(self.current_table, record['idx'])
            self.parent_window.on_data_changed()
            QMessageBox.information(
                self, "删除成功",
                f"已删除 {self.current_table}[{record['idx']}]"
            )
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"无法删除记录:\n{str(e)}")
    def copy_selected(self):
        """复制选中记录到其他表"""
        fw = self.parent_window.fw
        if not fw:
            return
        
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        
        if record['type'] not in ('valid', 'reserved'):
            QMessageBox.warning(
                self, "不允许复制",
                f"{self.current_table}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许复制"
            )
            return
        
        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return
        
        # 弹出复制对话框
        dialog = CopyRecordDialog(self, fw, self.current_table, record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()



class LogicalTableView(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.current_group = None
        self.groups_data = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("介质类型分组:"))
        self.group_list = QListWidget()
        self.group_list.currentTextChanged.connect(self.on_group_changed)
        left_layout.addWidget(self.group_list)
        left_panel.setLayout(left_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        self.group_info_label = QLabel()
        right_layout.addWidget(self.group_info_label)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels([
            'MID', '介质类型', '物理位置', '速度', '参数', 'Excel 参考'
        ])
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.doubleClicked.connect(self.on_row_double_clicked)
        right_layout.addWidget(self.table_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("新增记录")
        self.add_btn.clicked.connect(self.add_record)
        btn_layout.addWidget(self.add_btn)
        self.edit_btn = QPushButton("编辑选中记录")
        self.edit_btn.clicked.connect(self.edit_selected)
        btn_layout.addWidget(self.edit_btn)
        self.delete_btn = QPushButton("删除选中记录")
        self.delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.delete_btn)
        self.copy_btn = QPushButton("复制到...")
        self.copy_btn.clicked.connect(self.copy_selected)
        btn_layout.addWidget(self.copy_btn)
        self.detail_btn = QPushButton("查看详情")
        self.detail_btn.clicked.connect(self.show_selected_detail)
        btn_layout.addWidget(self.detail_btn)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        right_panel.setLayout(right_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def load_groups(self, fw, keep_group=True):
        previous_group = self.current_group if keep_group else None

        self.group_list.blockSignals(True)
        self.group_list.clear()
        self.table_widget.setRowCount(0)
        self.group_info_label.setText("")

        if not fw:
            self.groups_data = {}
            self.current_group = None
            self.group_list.blockSignals(False)
            return

        self.groups_data = fw.logical_groups(include_empty=True)

        target_row = 0
        for row, group_name in enumerate(sorted(self.groups_data.keys())):
            count = len(self.groups_data[group_name])
            self.group_list.addItem(f"{group_name} ({count})")
            if previous_group and group_name == previous_group:
                target_row = row

        self.group_list.blockSignals(False)

        if self.group_list.count() > 0:
            self.group_list.setCurrentRow(target_row)
            self.on_group_changed(self.group_list.currentItem().text())

    def on_group_changed(self, text):
        if not text:
            return

        group_name = text.rsplit(' (', 1)[0]
        self.current_group = group_name

        if group_name not in self.groups_data:
            self.table_widget.setRowCount(0)
            self.group_info_label.setText("")
            return

        records = self.groups_data[group_name]
        self.group_info_label.setText(f"{group_name}: {len(records)} 条记录")
        self.table_widget.setRowCount(len(records))

        for row, record in enumerate(records):
            if record['type'] == 'valid':
                mid_text = record['mid']
                if record['deleted']:
                    mid_text += " [已删除]"
            else:
                mid_text = display_raw_mid(record['mid_raw'])
            mid_item = QTableWidgetItem(mid_text)
            self.table_widget.setItem(row, 0, mid_item)

            media_item = QTableWidgetItem(format_candidates(record['candidates']))
            self.table_widget.setItem(row, 1, media_item)

            location_text = f"{record['table']}[{record['idx']}] @0x{record['off']:05X}"
            location_item = QTableWidgetItem(location_text)
            self.table_widget.setItem(row, 2, location_item)

            if record['type'] == 'valid' and len(record['params']) >= 2:
                speed_byte = record['params'][1]
                speed_text = f"0x{speed_byte:02X} {display_speed(speed_byte)}"
            else:
                speed_text = "-"
            speed_item = QTableWidgetItem(speed_text)
            self.table_widget.setItem(row, 3, speed_item)

            params_item = QTableWidgetItem(record['params'].hex())
            self.table_widget.setItem(row, 4, params_item)

            if record['candidates'] and len(record['candidates']) == 1:
                c = record['candidates'][0]
                ref_text = f"{c['display']} / {c['capacity']} / {c['layers']}"
            else:
                ref_text = "-"
            ref_item = QTableWidgetItem(ref_text)
            self.table_widget.setItem(row, 5, ref_item)

            color = get_record_color(record)
            text_color = QColor(0, 0, 0)
            for col in range(6):
                item = self.table_widget.item(row, col)
                if item:
                    item.setBackground(QBrush(color))
                    item.setForeground(QBrush(text_color))

    def current_record(self):
        if not self.current_group or self.current_group not in self.groups_data:
            return None
        row = self.table_widget.currentRow()
        if row < 0:
            return None
        records = self.groups_data[self.current_group]
        if row >= len(records):
            return None
        return records[row]

    def on_row_double_clicked(self, index):
        self.edit_selected()

    def show_selected_detail(self):
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        dialog = RecordDetailDialog(self, record['table'], record)
        dialog.exec()

    def add_record(self):
        fw = self.parent_window.fw
        if not fw:
            return

        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return

        dialog = RecordAddDialog(self, fw)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()



    def edit_selected(self):
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        fw = self.parent_window.fw
        if not fw:
            return
        if record['type'] in ('zero', 'invalid'):
            QMessageBox.warning(self, "不允许编辑", f"{record['table']}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许编辑")
            return
        if record['type'] == 'empty':
            QMessageBox.information(self, "提示", f"{record['table']}[{record['idx']}] 是全 FF 空槽，请使用「新增记录」功能")
            return
        if not fw.exact:
            QMessageBox.warning(self, "不允许编辑", f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}")
            return
        dialog = RecordEditDialog(self, fw, record['table'], record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()

    def delete_selected(self):
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        fw = self.parent_window.fw
        if not fw:
            return
        if record['type'] not in ('valid', 'reserved'):
            QMessageBox.warning(self, "不允许删除", f"{record['table']}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许删除")
            return
        if not fw.exact:
            QMessageBox.warning(self, "不允许编辑", f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}")
            return
        mid_display = record['mid'] if record['type'] == 'valid' else '[保留槽位]'
        reply = QMessageBox.question(self, "确认删除", f"确定要删除以下记录吗？\n\n物理表: {record['table']}[{record['idx']}]\nMID: {mid_display}\n偏移: 0x{record['off']:05X}\n\n删除后该槽位将变为全 FF 空槽。", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            fw.delete_record(record['table'], record['idx'])
            self.parent_window.on_data_changed()
            QMessageBox.information(self, "删除成功", f"已删除 {record['table']}[{record['idx']}]")
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"无法删除记录:\n{str(e)}")

    def copy_selected(self):
        """复制选中记录到其他表"""
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return
        
        fw = self.parent_window.fw
        if not fw:
            return
        
        if record['type'] not in ('valid', 'reserved'):
            QMessageBox.warning(
                self, "不允许复制",
                f"{record['table']}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许复制"
            )
            return
        
        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return
        
        # 弹出复制对话框
        dialog = CopyRecordDialog(self, fw, record['table'], record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.fw = None
        self.fw_path = None
        self.is_modified = False
        self.setWindowTitle("LG MT1959 固件编辑器 v1.0")
        self.setGeometry(100, 100, 1400, 800)
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.update_window_title()
        self.update_ui_state()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel = self.create_info_panel()
        splitter.addWidget(left_panel)
        right_panel = self.create_content_panel()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)

    def create_info_panel(self):
        panel = QGroupBox("固件信息")
        layout = QVBoxLayout()
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumWidth(300)
        self.info_text.setPlainText("未打开固件")
        layout.addWidget(self.info_text)
        panel.setLayout(layout)
        return panel

    def create_content_panel(self):
        self.content_tabs = QTabWidget()
        self.physical_view = PhysicalTableView(self)
        self.content_tabs.addTab(self.physical_view, "物理视图")
        self.logical_view = LogicalTableView(self)
        self.content_tabs.addTab(self.logical_view, "逻辑视图")
        return self.content_tabs

    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开固件(&O)...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_firmware)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        save_action = QAction("保存(&S)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_firmware)
        save_action.setEnabled(False)
        self.save_action = save_action
        file_menu.addAction(save_action)
        save_as_action = QAction("另存为(&A)...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_firmware)
        save_as_action.setEnabled(False)
        self.save_as_action = save_as_action
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        close_action = QAction("关闭固件(&C)", self)
        close_action.triggered.connect(self.close_firmware)
        close_action.setEnabled(False)
        self.close_action = close_action
        file_menu.addAction(close_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        edit_menu = menubar.addMenu("编辑(&E)")
        
        add_record_action = QAction("新增记录(&A)...", self)
        add_record_action.triggered.connect(self.menu_add_record)
        edit_menu.addAction(add_record_action)
        
        edit_record_action = QAction("编辑记录(&E)...", self)
        edit_record_action.triggered.connect(self.menu_edit_record)
        edit_menu.addAction(edit_record_action)
        
        delete_record_action = QAction("删除记录(&D)", self)
        delete_record_action.triggered.connect(self.menu_delete_record)
        edit_menu.addAction(delete_record_action)
        edit_menu.addSeparator()
        edit_menu.addAction("复制参数(&C)")
        tool_menu = menubar.addMenu("工具(&T)")
        replace_from_action = QAction("WSR 替换自其他固件(&F)...", self)
        replace_from_action.triggered.connect(self.replace_wsr_from)
        tool_menu.addAction(replace_from_action)
        
        replace_to_action = QAction("WSR 替换到其他固件(&T)...", self)
        replace_to_action.triggered.connect(self.replace_wsr_to)
        tool_menu.addAction(replace_to_action)
        tool_menu.addAction("恢复默认 MID 列表(&R)...")
        tool_menu.addSeparator()
        tool_menu.addAction("导出列表(&E)...")
        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.addAction("关于(&A)")

    def setup_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        open_btn = QAction("打开固件", self)
        open_btn.triggered.connect(self.open_firmware)
        toolbar.addAction(open_btn)
        toolbar.addSeparator()
        save_btn = QAction("保存", self)
        save_btn.triggered.connect(self.save_firmware)
        save_btn.setEnabled(False)
        self.toolbar_save_btn = save_btn
        toolbar.addAction(save_btn)
        save_as_btn = QAction("另存为", self)
        save_as_btn.triggered.connect(self.save_as_firmware)
        save_as_btn.setEnabled(False)
        self.toolbar_save_as_btn = save_as_btn
        toolbar.addAction(save_as_btn)
        toolbar.addSeparator()
        close_btn = QAction("关闭", self)
        close_btn.triggered.connect(self.close_firmware)
        close_btn.setEnabled(False)
        self.toolbar_close_btn = close_btn
        toolbar.addAction(close_btn)

    def setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

    def update_window_title(self):
        title = "LG MT1959 固件编辑器 v1.0"
        if self.fw_path:
            filename = os.path.basename(self.fw_path)
            title = f"{filename} - {title}"
            if self.is_modified:
                title = f"*{title}"
        self.setWindowTitle(title)

    def update_ui_state(self):
        has_fw = self.fw is not None
        self.save_action.setEnabled(has_fw and self.is_modified)
        self.save_as_action.setEnabled(has_fw)
        self.close_action.setEnabled(has_fw)
        self.toolbar_save_btn.setEnabled(has_fw and self.is_modified)
        self.toolbar_save_as_btn.setEnabled(has_fw)
        self.toolbar_close_btn.setEnabled(has_fw)

    def on_data_changed(self):
        self.is_modified = True
        self.update_window_title()
        self.update_ui_state()
        self.display_firmware_info()
        self.physical_view.load_table(self.fw, self.physical_view.current_table)
        self.logical_view.load_groups(self.fw, keep_group=True)
        self.status.showMessage("固件已修改")


    def on_delete_record(self):
        """菜单栏-删除选定记录"""
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # 物理表视图
            self.physical_view.delete_selected()
        elif current_tab == 1:  # 逻辑视图
            self.logical_view.delete_selected()

    def open_firmware(self):
        if self.is_modified:
            reply = QMessageBox.question(
                self, "未保存的改动",
                "当前固件有未保存的改动，是否继续打开新固件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开固件", "", "固件文件 (*.bin);;所有文件 (*.*)"
        )
        if not file_path:
            return
        try:
            self.status.showMessage("正在加载固件...")
            QApplication.processEvents()
            fw = Firmware(file_path)
            self.fw = fw
            self.fw_path = file_path
            self.is_modified = False
            self.display_firmware_info()
            self.physical_view.load_table(fw, 'BD-XL')
            self.logical_view.load_groups(fw)
            self.update_window_title()
            self.update_ui_state()
            self.status.showMessage(f"已加载: {os.path.basename(file_path)}")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            QMessageBox.critical(self, "加载失败", f"无法加载固件:\n{error_detail}")
            self.status.showMessage("加载失败")
            print(error_detail)

    def display_firmware_info(self):
        if not self.fw:
            self.info_text.setPlainText("未打开固件")
            return
        fw = self.fw
        info = []
        info.append(f"文件名: {os.path.basename(self.fw_path)}")
        info.append(f"大小: {len(fw.blob):,} 字节")
        info.append("")
        info.append(f"WSR 起点: 0x{fw.ws:06X}")
        info.append(f"WSR 终点: 0x{fw.we:06X}")
        info.append(f"WSR 硬边界: 0x{fw.hard:06X}")
        info.append("")
        info.append(f"压缩流: {fw.orig_len} 字节")
        info.append(f"可用空间: {fw.avail} 字节")
        info.append(f"明文: {len(fw.plain)} 字节")
        info.append("")
        info.append(f"压缩自检: {fw.exact_info}")
        info.append("")
        if not fw.exact:
            info.append("⚠ 警告:")
            info.append("该固件不能被当前压缩器")
            info.append("逐字节复现，只允许查看，")
            info.append("不允许编辑。")
        else:
            info.append("✓ 该固件可以安全编辑")
        info.append("")
        info.append(f"是否已修改: {'是' if self.is_modified else '否'}")
        self.info_text.setPlainText("\n".join(info))

    def save_firmware(self):
        if not self.fw or not self.is_modified:
            return
        reply = QMessageBox.question(
            self, "确认保存",
            "是否原地保存固件？\n原文件将自动备份为 .bak",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            ok, msg = self.fw.save(inplace=True)
            if ok:
                self.is_modified = False
                self.update_window_title()
                self.update_ui_state()
                self.display_firmware_info()
                QMessageBox.information(self, "保存成功", msg)
                self.status.showMessage("保存成功")
            else:
                QMessageBox.critical(self, "保存失败", msg)
                self.status.showMessage("保存失败")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存时发生错误:\n{str(e)}")

    def save_as_firmware(self):
        if not self.fw:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "", "固件文件 (*.bin);;所有文件 (*.*)"
        )
        if not file_path:
            return
        try:
            ok, msg = self.fw.save(output=file_path, inplace=False)
            if ok:
                self.is_modified = False
                self.update_window_title()
                self.update_ui_state()
                self.display_firmware_info()
                QMessageBox.information(self, "保存成功", msg)
                self.status.showMessage(f"已保存到: {os.path.basename(file_path)}")
            else:
                QMessageBox.critical(self, "保存失败", msg)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存时发生错误:\n{str(e)}")

    def close_firmware(self):
        if self.is_modified:
            reply = QMessageBox.question(
                self, "未保存的改动",
                "当前固件有未保存的改动，是否保存？",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.save_firmware()
                if self.is_modified:
                    return
        self.fw = None
        self.fw_path = None
        self.is_modified = False
        self.info_text.setPlainText("未打开固件")
        self.physical_view.load_table(None, 'BD-XL')
        self.logical_view.load_groups(None)
        self.update_window_title()
        self.update_ui_state()
        self.status.showMessage("已关闭固件")

    def closeEvent(self, event):
        if self.is_modified:
            reply = QMessageBox.question(
                self, "未保存的改动",
                "当前固件有未保存的改动，是否保存？",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.save_firmware()
                if self.is_modified:
                    event.ignore()
                    return
        event.accept()
    def menu_add_record(self):
        current_tab = self.content_tabs.currentWidget()
        if current_tab == self.physical_view:
            self.physical_view.add_record()
        elif current_tab == self.logical_view:
            self.logical_view.add_record()
    
    def menu_edit_record(self):
        current_tab = self.content_tabs.currentWidget()
        if current_tab == self.physical_view:
            self.physical_view.edit_selected()
        elif current_tab == self.logical_view:
            self.logical_view.edit_selected()
    
    def menu_delete_record(self):
        current_tab = self.content_tabs.currentWidget()
        if current_tab == self.physical_view:
            self.physical_view.delete_selected()
        elif current_tab == self.logical_view:
            self.logical_view.delete_selected()


    def edit_selected(self):
        fw = self.parent_window.fw
        if not fw:
            return
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return

        if record['type'] in ('zero', 'invalid'):
            QMessageBox.warning(
                self, "不允许编辑",
                f"{record['table']}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许编辑"
            )
            return

        if record['type'] == 'empty':
            QMessageBox.information(
                self, "提示",
                f"{record['table']}[{record['idx']}] 是全 FF 空槽，请使用「新增记录」功能"
            )
            return

        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return

        dialog = RecordEditDialog(self, fw, record['table'], record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.parent_window.on_data_changed()


    def delete_selected(self):
        fw = self.parent_window.fw
        if not fw:
            return
        record = self.current_record()
        if not record:
            QMessageBox.information(self, "提示", "请先选中一行记录")
            return

        if record['type'] not in ('valid', 'reserved'):
            QMessageBox.warning(
                self, "不允许删除",
                f"{record['table']}[{record['idx']}] 是{TYPE_LABEL[record['type']]}，不允许删除"
            )
            return

        if not fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"该固件不能被当前压缩器逐字节复现：\n{fw.exact_info}"
            )
            return

        mid_display = record['mid'] if record['type'] == 'valid' else '[保留槽位]'
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除以下记录吗？\n\n"
            f"物理表: {record['table']}[{record['idx']}]\n"
            f"MID: {mid_display}\n"
            f"偏移: 0x{record['off']:05X}\n\n"
            f"删除后该槽位将变为全 FF 空槽。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            fw.delete_record(record['table'], record['idx'])
            self.parent_window.on_data_changed()
            QMessageBox.information(
                self, "删除成功",
                f"已删除 {record['table']}[{record['idx']}]"
            )
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"无法删除记录:\n{str(e)}")

    def replace_wsr_from(self):
        """从其他固件替换 WSR 到当前固件"""
        if not self.fw:
            QMessageBox.warning(self, "未打开固件", "请先打开一个固件文件")
            return
        
        if not self.fw.exact:
            QMessageBox.warning(
                self, "不允许编辑",
                f"当前固件不能被压缩器逐字节复现：\n{self.fw.exact_info}\n\n无法进行 WSR 替换"
            )
            return
        
        # 选择源固件文件
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择源固件文件",
            "",
            "固件文件 (*.bin);;所有文件 (*)"
        )
        
        if not source_path:
            return
        
        try:
            # 读取源固件
            source_fw = Firmware(source_path)
            
            if not source_fw.exact:
                reply = QMessageBox.question(
                    self,
                    "源固件警告",
                    f"源固件无法被压缩器逐字节复现：\n{source_fw.exact_info}\n\n"
                    f"可能导致 WSR 数据不完整或损坏。\n\n是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # 确认替换
            reply = QMessageBox.question(
                self,
                "确认替换",
                f"从源固件读取 WSR：\n{source_path}\n\n"
                f"替换到当前固件：\n{self.fw_path}\n\n"
                f"当前固件的所有 WSR 数据将被覆盖，确定继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
            
            # 执行替换
            self.fw.replace_plain(source_fw.plain)
            self.on_data_changed()
            
            QMessageBox.information(
                self,
                "替换成功",
                f"已从源固件替换 WSR 区域\n\n"
                f"源固件: {source_path}\n"
                f"目标固件: {self.fw_path}\n\n"
                f"请记得保存当前固件！"
            )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "替换失败",
                f"无法从源固件替换 WSR:\n{str(e)}"
            )
    
    def replace_wsr_to(self):
        """将当前固件的 WSR 替换到其他固件"""
        if not self.fw:
            QMessageBox.warning(self, "未打开固件", "请先打开一个固件文件")
            return
        
        if not self.fw.exact:
            QMessageBox.warning(
                self, "不允许导出",
                f"当前固件不能被压缩器逐字节复现：\n{self.fw.exact_info}\n\n"
                f"无法保证导出的 WSR 数据正确性"
            )
            return
        
        # 选择目标固件文件
        target_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择目标固件文件",
            "",
            "固件文件 (*.bin);;所有文件 (*)"
        )
        
        if not target_path:
            return
        
        try:
            # 读取目标固件
            target_fw = Firmware(target_path)
            
            if not target_fw.exact:
                reply = QMessageBox.question(
                    self,
                    "目标固件警告",
                    f"目标固件无法被压缩器逐字节复现：\n{target_fw.exact_info}\n\n"
                    f"替换后可能无法正常保存。\n\n是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            # 确认替换
            reply = QMessageBox.question(
                self,
                "确认替换",
                f"从当前固件读取 WSR：\n{self.fw_path}\n\n"
                f"替换到目标固件：\n{target_path}\n\n"
                f"目标固件的所有 WSR 数据将被覆盖，确定继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
            
            # 执行替换
            target_fw.replace_plain(self.fw.plain)
            
            # 选择输出文件
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存替换后的固件",
                target_path.replace('.bin', '_wsr_replaced.bin'),
                "固件文件 (*.bin);;所有文件 (*)"
            )
            
            if not output_path:
                return
            
            # 保存文件
            success, msg = target_fw.save(output_path)
            
            if not success:
                QMessageBox.critical(self, "保存失败", f"无法保存替换后的固件:\n{msg}")
                return
            
            QMessageBox.information(
                self,
                "替换成功",
                f"已将当前 WSR 替换到目标固件\n\n"
                f"源 WSR: {self.fw_path}\n"
                f"目标固件: {target_path}\n"
                f"输出文件: {output_path}"
            )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "替换失败",
                f"无法替换 WSR 到目标固件:\n{str(e)}"
            )
    

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
