# fw_core.py
import os
import shutil
from collections import defaultdict
from datetime import datetime

WIN = 0x1000
DELETED_MID = "XXXXXXXXX"

TABLES = [
    {"name": "BD-XL", "start": 0x3C00, "end": 0x3DF8, "stride": 21, "desc": "21-byte physical region"},
    {"name": "15B-A", "start": 0x3E00, "end": 0x3EC3, "stride": 15, "desc": "15-byte physical region A"},
    {"name": "15B-B", "start": 0x3EC3, "end": 0x3FD1, "stride": 15, "desc": "15-byte physical region B"},
    {"name": "15B-C", "start": 0x3FD1, "end": 0x4382, "stride": 15, "desc": "15-byte physical region C"},
    {"name": "15B-D", "start": 0x4382, "end": 0x4634, "stride": 15, "desc": "15-byte physical region D"},
]

TYPE_LABEL = {"valid": "有效", "reserved": "占位", "empty": "空槽", "zero": "全零", "invalid": "异常"}

def normalize_text_mid(value):
    if isinstance(value, bytes):
        value = value.decode("ascii", "replace")
    value = value.upper().replace("-", "").replace("_", "").replace(" ", "").replace("\x00", "")
    return value

def normalize_raw_mid(raw):
    return normalize_text_mid(bytes(raw).rstrip(b"\x00 "))

def display_raw_mid(raw):
    result = []
    for bv in bytes(raw):
        if bv == 0x00: result.append('_')
        elif bv == 0xFF: result.append('.')
        elif 0x20 <= bv < 0x7F: result.append(chr(bv))
        else: result.append('.')
    return ''.join(result)

def display_speed(sv):
    sn = [(0x02,'2x'),(0x04,'4x'),(0x08,'6x'),(0x10,'8x'),(0x20,'10x'),(0x40,'12x'),(0x80,'16x')]
    r = [n for b,n in sn if sv & b]
    return '/'.join(r) if r else '-'

def add_media_row(db, key, disp, mt, cap, lay, rec, ns):
    row = {"key": key, "display": disp, "media_type": mt, "capacity": cap, "layers": lay, "recording": rec, "nominal_speed": ns}
    ex = db.setdefault(key, [])
    sig = (row["media_type"], row["capacity"], row["layers"], row["recording"], row["nominal_speed"])
    for old in ex:
        if (old["media_type"], old["capacity"], old["layers"], old["recording"], old["nominal_speed"]) == sig:
            return
    ex.append(row)

def build_media_database():
    db = {}
    for k, d, s, r in [
        ("CMCMAGBA2","CMCMAG-BA2","1-2X","HTL"),("CMCMAGBA3","CMCMAG-BA3","1-4X","HTL"),("CMCMAGBA5","CMCMAG-BA5","1-6X","HTL"),
        ("VERBATIMA","VERBAT-IMa","1-2X","HTL"),("VERBATIMC","VERBAT-IMc","1-4X","HTL"),("VERBATIME","VERBAT-IMe","1-6X","HTL"),
        ("VERBATIMW","VERBAT-IMw","1-2X","LTH"),("VERBATIMV","VERBAT-IMv","1-4X","LTH"),("VERBATIMU","VERBAT-IMu","1-6X","LTH"),
        ("MAXELLRS2","MAXELL-RS2","1-6X","LTH"),("INFOMER20","INFOME-R20","1-2X","HTL"),("INFOMER30","INFOME-R30","1-4X","HTL"),
        ("INFOMER40","INFOME-R40","1-6X","HTL"),("LGEBRAS04","LGEBRA-S04","1-4X","HTL"),("LGEBRAS06","LGEBRA-S06","1-6X","HTL"),
        ("PHILIPR02","PHILIP-R02","1-2X","HTL"),("PHILIPR04","PHILIP-R04","1-4X","HTL"),("MBIR04","MBI-R04","1-4X","HTL"),
        ("MBIR06","MBI-R06","1-6X","HTL"),("PRODISCR0","PRODIS-CR0","1-4X","HTL"),("PRODISCR1","PRODIS-CR1","1-6X","HTL"),
        ("RITEKBR1","RITEK-BR1","1-2X","HTL"),("RITEKBR2","RITEK-BR2","1-4X","HTL"),("RITEKBR3","RITEK-BR3","1-6X","HTL"),
        ("RITEKBR4","RITEK-BR4","1-6X","HTL"),("RITEKBO1","RITEK-BO1","1-4X","LTH"),("RITEKBO2","RITEK-BO2","1-6X","LTH"),
        ("SONYNO1","SONY-NO1","1-2X","HTL"),("SONYNN1","SONY-NN1","1-2X","HTL"),("SONYNN2","SONY-NN2","1-4X","HTL"),
        ("SONYNN3","SONY-NN3","1-6X","HTL"),("TDKBLDRDA","TDKBLD-RDA","1-2X","HTL"),("TDKBLDRBA","TDKBLD-RBA","1-2X","HTL"),
        ("TDKBLDRBB","TDKBLD-RBB","1-4X","HTL"),("TDKBLDRBD","TDKBLD-RBD","1-6X","HTL"),("JVCAMS6L","JVC-AM-S6L","1-6X","LTH"),
        ("OTCBDR001","OTCBDR-1","1-4X","HTL"),("OTCBDR002","OTCBDR-2","1-6X","HTL"),("UMEBDR014","UMEBDR-14","4X","HTL"),
        ("UMEBDR016","UMEBDR-16","6X","HTL"),("ISMMBDR01","ISMMBDR-R01","1-4X","HTL"),("MILLENMR1","MILLEN-MR1","1-4X","HTL"),
    ]: add_media_row(db, k, d, "BD-R SL 25GB", "25GB", "SL", r, s)
    
    for k, d, s, r in [
        ("VERBATIMB","VERBAT-IMb","1-2X","HTL"),("VERBATIMD","VERBAT-IMd","1-4X","HTL"),("VERBATIMF","VERBAT-IMf","1-6X","HTL"),
        ("VAMKMIMF","VAMKM-IMf","1-6X","HTL"),("CMCMAGDI6","CMCMAG-DI6","1-6X","HTL"),("RITEKDR2","RITEK-DR2","1-4X","HTL"),
        ("RITEKDR3","RITEK-DR3","1-6X","HTL"),("SONYND4","SONY-ND4","1-4X","HTL"),("SONYND6","SONY-ND6","1-6X","HTL"),
        ("TDKBLDRFA","TDKBLD-RFA","1-2X","HTL"),("TDKBLDRFB","TDKBLD-RFB","1-4X","HTL"),("TDKBLDRFD","TDKBLD-RFD","1-6X","HTL"),
    ]: add_media_row(db, k, d, "BD-R DL 50GB", "50GB", "DL", r, s)
    
    for k, d in [("VERBATIMK","VERBAT-IMk"),("VAMKMIMK","VAMKM-IMk"),("CMCMAGTIF","CMCMAG-TIF"),("PANRC4","PAN-RC4"),
                  ("RITEKTL2","RITEK-TL2"),("TDKBLDRNC","TDKBLD-RNC")]:
        add_media_row(db, k, d, "BD-R XL TL 100GB", "100GB", "TL", "HTL", "2-4X")
    
    for k, d in [("SONYNQ1","SONY-NQ1"),("SONYNQ2","SONY-NQ2"),("TDKBLDROC","TDKBLD-ROC")]:
        add_media_row(db, k, d, "BD-R XL QL 128GB", "128GB", "QL", "HTL", "2-4X")
    
    for k, d in [("VERBATIM0","VERBAT-IM0"),("CMCMAGCN2","CMCMAG-CN2"),("MAXELLES1","MAXELL-ES1"),("LGEBRES01","LGEBRE-S01"),
                  ("PHILIPW02","PHILIP-W02"),("MBIE02","MBI-E02"),("RITEKBW1","RITEK-BW1"),("SONYES1","SONY-ES1"),
                  ("TDKBLDWDA","TDKBLD-WDA"),("TDKBLDWBA","TDKBLD-WBA"),("INFOMEE20","INFOME-E20"),("OTCBRE001","OTCBRE-001")]:
        add_media_row(db, k, d, "BD-RE SL 25GB", "25GB", "SL", "HTL", "1-2X")
    
    for k, d in [("VERBATIM1","VERBAT-IM1"),("RITEKDW1","RITEK-DW1"),("SONYED4","SONY-ED4"),("TDKBLDWFA","TDKBLD-Wfa")]:
        add_media_row(db, k, d, "BD-RE DL 50GB", "50GB", "DL", "HTL", "1-2X")
    
    for k, d, s in [("VERBATIM4","VERBAT-IM4","2X"),("PANEC2","PAN-EC2","1-2X"),("SONYET1","SONY-ET1","2X"),("SONYET2","SONY-ET2","2X")]:
        add_media_row(db, k, d, "BD-RE XL TL 100GB", "100GB", "TL", "HTL", s)
    
    add_media_row(db,"MEIT01","MEI-T01","BD-R SL 25GB","25GB","SL","HTL","1-2X")
    add_media_row(db,"MEIT01","MEI-T01","BD-R DL 50GB","50GB","DL","HTL","1-2X")
    add_media_row(db,"MEIT02","MEI-T02","BD-R SL 25GB","25GB","SL","HTL","1-4X")
    add_media_row(db,"MEIT02","MEI-T02","BD-R DL 50GB","50GB","DL","HTL","1-4X")
    add_media_row(db,"MEIRA1","MEI-RA1","BD-R SL 25GB","25GB","SL","HTL","1-6X")
    add_media_row(db,"MEIRB1","MEI-RB1","BD-R DL 50GB","50GB","DL","HTL","1-6X")
    return db

MEDIA_DATABASE = build_media_database()

def media_candidates_for_raw(raw):
    return list(MEDIA_DATABASE.get(normalize_raw_mid(raw), []))

def locate_wsr(blob):
    sig = blob.find(b"OOB WSR")
    if sig < 0: raise ValueError("未找到 OOB WSR 签名")
    ws = sig - 1
    probe = ws
    while probe + 0x40 <= len(blob):
        if blob[probe:probe+0x40] == b"\xFF"*0x40: break
        probe += 1
    we = probe
    while we > ws and blob[we-1] == 0xFF: we -= 1
    hard = probe
    while hard < len(blob) and blob[hard] == 0xFF: hard += 1
    return ws, we, hard

def decompress(data):
    out, src, win, total = bytearray(), 0, 0, len(data)
    while src < total:
        ctrl, src, mask = data[src], src+1, 0x80
        for _ in range(8):
            if src >= total: break
            if ctrl & mask:
                out.append(data[src]); src += 1
            else:
                if src+1 >= total: raise ValueError("匹配 token 不完整")
                b1, b2, src = data[src], data[src+1], src+2
                ln, d = (b1 >> 4) + 3, ((b1 & 0x0F) << 8) | b2
                pos = len(out) - win - d - 1
                for k in range(ln):
                    s = win + pos + k
                    out.append(out[s] if 0 <= s < len(out) else 0)
            win, mask = max(0, len(out) - WIN), mask >> 1
    return bytes(out)

def compress(plain):
    plain = bytes(plain)
    if len(plain) < 4: raise ValueError("明文长度不足")
    if plain[-4:] != b"\x10\x10\x10\x10": raise ValueError("明文末尾不是 10 10 10 10")
    limit, toks, pos = len(plain) - 4, [], 0
    while pos < limit:
        wlo, maxl, bl, bd = max(0, pos-WIN), min(18, limit-pos), 0, None
        if maxl >= 3:
            for dist in range(pos-wlo, 0, -1):
                dc = dist - 1
                if dc == 0 or dc > 0xFFF: continue
                cap = min(maxl, dist-1)
                if cap < 3: continue
                sp, l = pos - dist, 0
                while l < cap and plain[sp+l] == plain[pos+l]: l += 1
                if l >= 3 and l > bl: bl, bd = l, dc
        if bl >= 3: toks.append(('m', bl, bd)); pos += bl
        else: toks.append(('l', plain[pos])); pos += 1
    toks.append(('m', 4, 0))
    res, prev = bytearray(), 0
    for g in range(0, len(toks), 8):
        grp, ctrl = toks[g:g+8], prev
        for slot in range(8):
            if slot < len(grp):
                ctrl = (ctrl | (0x80>>slot)) if grp[slot][0]=='l' else (ctrl & ~(0x80>>slot) & 0xFF)
        res.append(ctrl)
        for t in grp:
            if t[0]=='l': res.append(t[1])
            else: _, ln, dc = t; res.append(((ln-3)<<4)|((dc>>8)&0x0F)); res.append(dc&0xFF)
        prev = ctrl
    return bytes(res)

def classify_record(rec, stride):
    rec, mid = bytes(rec), bytes(rec[:9])
    if rec == b"\xFF" * stride: return "empty"
    if mid == b"\xFF" * 9: return "reserved"
    if mid == b"\x00" * 9: return "zero"
    if not all(v == 0 or 0x20 <= v < 0x7F for v in mid): return "invalid"
    first = mid[0]
    if not (0x30 <= first <= 0x39 or 0x41 <= first <= 0x5A or 0x61 <= first <= 0x7A): return "invalid"
    return "valid"

class Firmware:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as h: self.blob = h.read()
        self.dirty = False
        self.ws, self.we, self.hard = locate_wsr(self.blob)
        self.orig_comp = bytes(self.blob[self.ws:self.we])
        self.orig_len, self.avail = len(self.orig_comp), self.hard - self.ws
        self.plain = bytearray(decompress(self.orig_comp))
        regen = compress(bytes(self.plain))
        self.exact = regen == self.orig_comp
        if self.exact: self.exact_info = "逐字节一致"
        else:
            common = min(len(regen), len(self.orig_comp))
            dc = sum(1 for i in range(common) if regen[i] != self.orig_comp[i])
            self.exact_info = f"{dc} 处差异，长度 {len(regen)} vs {len(self.orig_comp)}"
        self.reload()
    
    def reload(self):
        self.tables = {}
        for cfg in TABLES:
            st, ed, stride, cap = cfg["start"], cfg["end"], cfg["stride"], (cfg["end"]-cfg["start"])//cfg["stride"]
            recs = []
            for idx in range(cap):
                off = st + idx * stride
                rec = bytes(self.plain[off:off+stride])
                rt = classify_record(rec, stride)
                mr = rec[:9]
                cands = media_candidates_for_raw(mr)
                mid = mr.rstrip(b"\x00 ").decode("ascii","replace") if rt == "valid" else ""
                recs.append({"table": cfg["name"], "idx": idx, "off": off, "type": rt, "mid": mid, "mid_raw": mr, 
                            "params": rec[9:], "candidates": cands, "deleted": mid==DELETED_MID})
            self.tables[cfg["name"]] = {"name": cfg["name"], "start": st, "end": ed, "stride": stride, 
                                        "capacity": cap, "desc": cfg["desc"], "records": recs}
    
    def table(self, name):
        if name not in self.tables: raise ValueError(f"未知物理表 {name}")
        return self.tables[name]
    
    def records(self, name): return self.table(name)["records"]
    
    def get_record(self, name, index):
        t = self.table(name)
        if not 0 <= index < t["capacity"]: raise IndexError(f"{name} 索引 {index} 超出范围")
        return t["records"][index]
    
    def param_len(self, name): return self.table(name)["stride"] - 9
    
    def require_supported(self):
        if not self.exact: raise ValueError(f"该固件不能被当前压缩器逐字节复现：{self.exact_info}")
    
    def media_group_for_record(self, r):
        if r["type"] != "valid": return None
        cands = r["candidates"]
        if len(cands) == 0: return "未知"
        if len(cands) > 1: return "类型有歧义"
        return cands[0]["media_type"]
    
    def logical_groups(self, include_empty=True):
        grps = defaultdict(list)
        for cfg in TABLES:
            for r in self.records(cfg["name"]):
                rt = r["type"]
                if rt == "valid": grps[self.media_group_for_record(r)].append(r)
                elif rt == "reserved": grps["未命名预设槽"].append(r)
                elif rt == "zero": grps["特殊全零槽"].append(r)
                elif rt == "invalid": grps["异常槽"].append(r)
                elif include_empty and rt == "empty": grps["空槽"].append(r)
        return dict(grps)
    
    def set_record(self, tn, idx, mid=None, params=None):
        self.require_supported()
        t, r = self.table(tn), self.get_record(tn, idx)
        if r["type"] in ("zero","invalid"): raise ValueError(f"{tn}[{idx}] 是{TYPE_LABEL[r['type']]}，不允许编辑")
        if r["type"] == "empty" and (mid is None or params is None): raise ValueError(f"{tn}[{idx}] 是空槽，需同时提供 MID 和参数")
        stride, plen, off = t["stride"], t["stride"]-9, r["off"]
        if mid is not None:
            em = mid.encode("ascii")
            if len(em) > 9: raise ValueError("MID 最多 9 个 ASCII 字符")
            self.plain[off:off+9] = em + b"\x00"*(9-len(em))
        if params is not None:
            params = bytes(params)
            if len(params) != plen: raise ValueError(f"{tn} 参数必须是 {plen} 字节")
            self.plain[off+9:off+stride] = params
        self.dirty = True
        self.reload()
    
    def delete_record(self, tn, idx):
        self.require_supported()
        r = self.get_record(tn, idx)
        if r["type"] in ("empty","zero","invalid"): raise ValueError(f"{tn}[{idx}] 不是可删除的记录")
        stride, off = self.table(tn)["stride"], r["off"]
        self.plain[off:off+stride] = b"\xFF" * stride
        self.dirty = True
        self.reload()

    def copy_record(self, src_table, src_idx, dst_table, dst_slot):
        """在本固件内复制记录"""
        self.require_supported()
        
        # 获取源记录
        src_rec = self.get_record(src_table, src_idx)
        if src_rec['type'] not in ('valid', 'reserved'):
            raise ValueError(f"{src_table}[{src_idx}] 不是可复制的记录")
        
        # 获取目标记录
        dst_rec = self.get_record(dst_table, dst_slot)
        
        # 获取表信息
        src_stride = self.table(src_table)['stride']
        dst_stride = self.table(dst_table)['stride']
        
        # 读取源记录的完整数据
        src_off = src_rec['off']
        src_data = bytes(self.plain[src_off:src_off+src_stride])
        
        # 处理长度差异
        if src_stride > dst_stride:
            new_data = src_data[:dst_stride]  # 截断
        elif src_stride < dst_stride:
            new_data = src_data + b'\xff' * (dst_stride - src_stride)  # 补齐
        else:
            new_data = src_data
        
        # 写入目标槽位
        dst_off = dst_rec['off']
        self.plain[dst_off:dst_off+dst_stride] = new_data
        self.dirty = True
        self.reload()

    def add_record(self, tn, mid, params, slot=None):
        self.require_supported()
        t, plen = self.table(tn), self.table(tn)["stride"]-9
        params = bytes(params)
        if len(params) != plen: raise ValueError(f"{tn} 参数必须是 {plen} 字节")
        empties = [r for r in t["records"] if r["type"]=="empty"]
        if not empties: raise ValueError(f"{tn} 无空槽")
        target = empties[0] if slot is None else next((r for r in empties if r["idx"]==slot), None)
        if target is None: raise ValueError(f"{tn}[{slot}] 不是空槽")
        em = mid.encode("ascii")
        if len(em) > 9: raise ValueError("MID 最多 9 个 ASCII 字符")
        off, stride = target["off"], t["stride"]
        self.plain[off:off+9] = em + b"\x00"*(9-len(em))
        self.plain[off+9:off+stride] = params
        self.dirty = True
        self.reload()
        return target["idx"]
    
    def copy_params(self, st, si, tt, ti):
        sr, tr = self.get_record(st, si), self.get_record(tt, ti)
        if sr["type"] in ("empty","zero","invalid"): raise ValueError("源记录不可复制")
        if tr["type"] in ("zero","invalid"): raise ValueError("目标槽不可编辑")
        if len(sr["params"]) != len(tr["params"]): raise ValueError("参数长度不同")
        self.set_record(tt, ti, params=sr["params"])
    
    def restore_mid_list(self, ref):
        self.require_supported()
        if not ref.exact: raise ValueError("参考固件不能复现")
        for cfg in TABLES:
            tn = cfg["name"]
            tt, st = self.table(tn), ref.table(tn)
            if tt["capacity"] != st["capacity"]: raise ValueError(f"{tn} 槽位数不同")
            for tr, sr in zip(tt["records"], st["records"]):
                self.plain[tr["off"]:tr["off"]+9] = ref.plain[sr["off"]:sr["off"]+9]
        self.dirty = True
        self.reload()
    
    def replace_plain(self, plain):
        self.require_supported()
        plain = bytes(plain)
        if len(plain) != len(self.plain): raise ValueError("明文长度不同")
        self.plain = bytearray(plain)
        self.dirty = True
        self.reload()
    
    def save(self, output=None, inplace=False):
        self.require_supported()
        if not self.dirty: return False, "没有改动"
        comp = compress(bytes(self.plain))
        if len(comp) > self.avail: return False, f"压缩流超出空间：{len(comp)} > {self.avail}"
        if decompress(comp) != bytes(self.plain): return False, "回读不一致"
        if inplace:
            if output and os.path.abspath(output) != os.path.abspath(self.path): return False, "--inplace 冲突"
            output = self.path
        elif not output:
            stem, ext = os.path.splitext(os.path.basename(self.path))
            output = f"{stem}_patched_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        nb = bytearray(self.blob)
        nb[self.ws:self.ws+len(comp)] = comp
        if self.ws+len(comp) < self.hard: nb[self.ws+len(comp):self.hard] = b"\xFF"*(self.hard-self.ws-len(comp))
        if len(nb) != len(self.blob) or nb[:self.ws] != self.blob[:self.ws] or nb[self.hard:] != self.blob[self.hard:]:
            return False, "完整性检查失败"
        bn = ""
        if inplace:
            bp = self._next_backup_path(self.path)
            shutil.copy2(self.path, bp)
            bn = f"\n已备份：{bp}"
        with open(output, "wb") as h: h.write(nb)
        chg = sum(1 for a,b in zip(nb, self.blob) if a!=b)
        return True, f"已保存：{output}\n文件大小：{len(nb)} 字节\n压缩流：{len(comp)} (原{self.orig_len}, {len(comp)-self.orig_len:+d})\n差异：{chg} 字节{bn}"
    
    @staticmethod
    def _next_backup_path(p):
        c, n = p+".bak", 1
        while os.path.exists(c): c, n = f"{p}.bak{n}", n+1
        return c

def clone_plain(sp, tfw, output=None, inplace=False):
    sfw = Firmware(sp)
    if not sfw.exact: return False, f"源固件不能复现：{sfw.exact_info}"
    if len(sfw.plain) != len(tfw.plain): return False, "明文长度不同"
    tfw.replace_plain(sfw.plain)
    return tfw.save(output, inplace=inplace)

def clone_raw(sp, tp, output=None, inplace=False):
    with open(sp,"rb") as h: sb = h.read()
    with open(tp,"rb") as h: tb = h.read()
    sws, swe, _ = locate_wsr(sb)
    tws, _, thard = locate_wsr(tb)
    sc, tcap = bytes(sb[sws:swe]), thard-tws
    if len(sc) > tcap: return False, f"源流超出空间：{len(sc)} > {tcap}"
    if inplace:
        if output and os.path.abspath(output) != os.path.abspath(tp): return False, "--inplace 冲突"
        output = tp
    elif not output:
        stem, ext = os.path.splitext(os.path.basename(tp))
        output = f"{stem}_cloned_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    nb = bytearray(tb)
    nb[tws:thard] = b"\xFF"*tcap
    nb[tws:tws+len(sc)] = sc
    if decompress(sc) != decompress(bytes(nb[tws:tws+len(sc)])): return False, "回读失败"
    bn = ""
    if inplace:
        bp = Firmware._next_backup_path(tp)
        shutil.copy2(tp, bp)
        bn = f"\n已备份：{bp}"
    with open(output, "wb") as h: h.write(nb)
    chg = sum(1 for a,b in zip(nb, tb) if a!=b)
    return True, f"已保存：{output}\n文件大小：{len(nb)} 字节\n复制流：{len(sc)} 字节\n差异：{chg} 字节{bn}"