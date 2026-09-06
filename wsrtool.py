# wsrtool.py
import argparse
import os
import sys

from fw_core import (
    TABLES,
    TYPE_LABEL,
    Firmware,
    clone_plain,
    clone_raw,
    display_raw_mid,
    display_speed,
)


def parse_parameter_hex(value, expected_length):
    try:
        data = bytes.fromhex(value)
    except ValueError:
        raise ValueError("参数不是合法十六进制")

    if len(data) != expected_length:
        raise ValueError(
            "参数应为 {} 字节，实际为 {} 字节".format(
                expected_length,
                len(data),
            )
        )

    return data


def parse_set_spec(spec, parameter_length):
    parts = spec.split(":")

    if len(parts) == 2:
        index = int(parts[0])
        value = parts[1]

        if len(value) == parameter_length * 2:
            try:
                params = bytes.fromhex(value)
                return index, None, params
            except ValueError:
                pass

        return index, value, None

    if len(parts) == 3:
        index = int(parts[0])
        mid = parts[1] if parts[1] else None
        params = None

        if parts[2]:
            params = parse_parameter_hex(
                parts[2],
                parameter_length,
            )

        return index, mid, params

    raise ValueError(
        "设置格式错误，应为 IDX:MID、IDX:PARAMS 或 IDX:MID:PARAMS"
    )


def parse_add_spec(spec, parameter_length):
    parts = spec.split(":")

    if len(parts) not in (2, 3):
        raise ValueError(
            "新增格式错误，应为 MID:PARAMS[:SLOT]"
        )

    mid = parts[0]
    params = parse_parameter_hex(parts[1], parameter_length)
    slot = int(parts[2]) if len(parts) == 3 else None

    return mid, params, slot


def parse_copy_spec(spec):
    text = spec.lower()

    if "to" not in text:
        raise ValueError(
            "复制格式错误，应为 SRCtoDST，例如 3to7"
        )

    left, right = text.split("to", 1)
    return int(left), int(right)


def candidates_text(record):
    candidates = record["candidates"]

    if not candidates:
        return "未知"

    values = []
    for candidate in candidates:
        text = "{} / {} / {} / {}".format(
            candidate["media_type"],
            candidate["capacity"],
            candidate["recording"],
            candidate["nominal_speed"],
        )
        if text not in values:
            values.append(text)

    return "；".join(values)


def record_mid_text(record):
    if record["type"] == "valid":
        if len(record["candidates"]) == 1:
            return record["candidates"][0]["display"]
        return record["mid"]

    return display_raw_mid(record["mid_raw"])


def current_speed_text(record):
    params = record["params"]
    if len(params) < 2:
        return "-"

    return "0x{:02X} {}".format(
        params[1],
        display_speed(params[1]),
    )


def show_physical_table(fw, table_name, hide_empty=False, marks=None):
    table = fw.table(table_name)
    records = table["records"]
    marks = marks or set()

    counts = {}
    for record in records:
        record_type = record["type"]
        counts[record_type] = counts.get(record_type, 0) + 1

    count_text = " ".join(
        "{}={}".format(TYPE_LABEL[key], counts[key])
        for key in sorted(counts)
    )

    print()
    print("[{}] {}".format(table_name, table["desc"]))
    print(
        "  明文范围 0x{:05X}-0x{:05X}  步长 {}  槽位 {}  {}".format(
            table["start"],
            table["end"],
            table["stride"],
            table["capacity"],
            count_text,
        )
    )

    print(
        "  {:>4} {:<5} {:<12} {:<24} {:<22} {}".format(
            "序号",
            "状态",
            "MID",
            "参数",
            "Excel类型",
            "当前速度位",
        )
    )
    print("  " + "-" * 112)

    for record in records:
        if hide_empty and record["type"] == "empty":
            continue

        mark = "  <<<" if record["idx"] in marks else ""
        label = TYPE_LABEL[record["type"]]

        if record["type"] == "empty":
            print(
                "  [{:2d}] {:<5}{}".format(
                    record["idx"],
                    label,
                    mark,
                )
            )
            continue

        mid = record_mid_text(record)
        params = record["params"].hex()
        candidates = candidates_text(record)
        speed = current_speed_text(record)

        if record["deleted"]:
            label = "已删"

        print(
            "  [{:2d}] {:<5} {:<12} {:<24} {:<22} {}{}".format(
                record["idx"],
                label,
                mid,
                params,
                candidates,
                speed,
                mark,
            )
        )


def show_all_physical(fw, hide_empty=False, marks=None):
    for config in TABLES:
        show_physical_table(
            fw,
            config["name"],
            hide_empty=hide_empty,
            marks=(marks or {}).get(config["name"], set()),
        )


def show_logical_view(fw, hide_empty=False):
    groups = fw.logical_groups(include_empty=not hide_empty)

    order = [
        "BD-R SL 25GB",
        "BD-R DL 50GB",
        "BD-R XL TL 100GB",
        "BD-R XL QL 128GB",
        "BD-RE SL 25GB",
        "BD-RE DL 50GB",
        "BD-RE XL TL 100GB",
        "类型有歧义",
        "未知",
        "未命名预设槽",
        "特殊全零槽",
        "异常槽",
        "空槽",
    ]

    group_names = []
    for name in order:
        if name in groups:
            group_names.append(name)

    for name in sorted(groups):
        if name not in group_names:
            group_names.append(name)

    print()
    print("=" * 118)
    print("按介质类型的逻辑视图")
    print("逻辑视图只用于查看和定位；编辑时使用右侧物理位置。")
    print("=" * 118)

    for group_name in group_names:
        records = groups[group_name]

        print()
        print("[{}] 共 {} 条".format(group_name, len(records)))
        print(
            "  {:>4} {:<14} {:<12} {:<12} {:<24} {}".format(
                "序号",
                "MID",
                "物理位置",
                "当前速度",
                "参数",
                "参考候选",
            )
        )
        print("  " + "-" * 112)

        for logical_index, record in enumerate(records):
            location = "{}[{}]".format(
                record["table"],
                record["idx"],
            )

            candidate_text = candidates_text(record)
            if group_name not in ("类型有歧义", "未知"):
                candidate_text = ""

            print(
                "  [{:3d}] {:<14} {:<12} {:<12} {:<24} {}".format(
                    logical_index,
                    record_mid_text(record),
                    location,
                    current_speed_text(record),
                    record["params"].hex(),
                    candidate_text,
                )
            )


def print_firmware_info(fw):
    print("固件：{}".format(fw.path))
    print("文件大小：{} 字节".format(len(fw.blob)))
    print(
        "WSR：0x{:06X}-0x{:06X}，有效压缩流 {} 字节".format(
            fw.ws,
            fw.we,
            fw.orig_len,
        )
    )
    print(
        "WSR 物理可用范围：0x{:06X}-0x{:06X}，共 {} 字节".format(
            fw.ws,
            fw.hard,
            fw.avail,
        )
    )
    print("解压明文：{} 字节".format(len(fw.plain)))
    print("原厂流自检：{}".format(fw.exact_info))

    if not fw.exact:
        print("警告：该固件不属于当前已确认的 MT1959 压缩格式。")
        print("当前只允许查看，不允许编辑或明文级克隆。")


def ensure_file(path, label):
    if not path:
        raise ValueError("{}路径为空".format(label))

    if not os.path.exists(path):
        raise FileNotFoundError(
            "{}不存在：{}".format(label, path)
        )


def save_edit_result(fw, args):
    ok, message = fw.save(
        args.output,
        inplace=args.inplace,
    )
    print()
    print(message)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(
        description="LG MT1959 WSR 固件工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
只读查看：
  python wsrtool.py a10ame.bin --list
  python wsrtool.py a10ame.bin --list --all
  python wsrtool.py a10ame.bin --list-by-type
  python wsrtool.py a10ame.bin --list-by-type --hide-empty

物理表编辑：
  python wsrtool.py a10ame.bin --table BD-XL --set 7:000e...
  python wsrtool.py a10ame.bin --table 15B-D --set 20:MYMID
  python wsrtool.py a10ame.bin --table 15B-D --del 20
  python wsrtool.py a10ame.bin --table 15B-D --add MID:参数
  python wsrtool.py a10ame.bin --table 15B-D --add MID:参数:46
  python wsrtool.py a10ame.bin --table BD-XL --copy 0to12

修改占位槽：
  python wsrtool.py a10ame.bin --table BD-XL --set 8:PANEC2

恢复默认 MID 字段列表：
  python wsrtool.py modified.bin --restore-mid-list a10ame.bin

WSR 克隆：
  python wsrtool.py target.bin --clone-from source.bin -o cloned.bin
  python wsrtool.py target.bin --clone-from source.bin --raw-clone -o cloned.bin

保存：
  默认输出新文件。
  --inplace 原地保存，并自动生成 .bak 备份。
        """,
    )

    parser.add_argument("input", help="输入固件")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--list-by-type", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--hide-empty", action="store_true")
    parser.add_argument("--table", default="BD-XL")
    parser.add_argument("--set", action="append", metavar="IDX:VAL")
    parser.add_argument("--del", dest="delete", action="append", type=int)
    parser.add_argument("--add", action="append", metavar="MID:PARAMS[:SLOT]")
    parser.add_argument("--copy", action="append", metavar="SRCtoDST")
    parser.add_argument("--restore-mid-list", metavar="REFERENCE.BIN")
    parser.add_argument("--clone-from", metavar="SOURCE.BIN")
    parser.add_argument("--raw-clone", action="store_true")
    parser.add_argument("-o", "--output")
    parser.add_argument("--inplace", action="store_true")

    args = parser.parse_args()

    try:
        ensure_file(args.input, "输入固件")

        has_edit_operation = any(
            [
                args.set,
                args.delete,
                args.add,
                args.copy,
                args.restore_mid_list,
                args.clone_from,
            ]
        )

        if args.clone_from and args.raw_clone:
            ensure_file(args.clone_from, "源固件")
            ok, message = clone_raw(
                args.clone_from,
                args.input,
                output=args.output,
                inplace=args.inplace,
            )
            print(message)
            return 0 if ok else 1

        fw = Firmware(args.input)
        print_firmware_info(fw)

        if args.clone_from:
            ensure_file(args.clone_from, "源固件")
            ok, message = clone_plain(
                args.clone_from,
                fw,
                output=args.output,
                inplace=args.inplace,
            )
            print()
            print(message)

            if ok:
                show_logical_view(fw, hide_empty=True)

            return 0 if ok else 1

        if args.restore_mid_list:
            ensure_file(args.restore_mid_list, "参考固件")
            reference = Firmware(args.restore_mid_list)
            fw.restore_mid_list(reference)
            return save_edit_result(fw, args)

        if args.list_by_type:
            show_logical_view(
                fw,
                hide_empty=args.hide_empty,
            )
            print()
            print("(只读模式，未写出任何文件)")
            return 0

        if not has_edit_operation:
            if args.all:
                show_all_physical(
                    fw,
                    hide_empty=args.hide_empty,
                )
            else:
                show_physical_table(
                    fw,
                    args.table,
                    hide_empty=args.hide_empty,
                )

            print()
            print("(只读模式，未写出任何文件)")
            return 0

        if not fw.exact:
            raise ValueError(
                "该固件不能进行当前编辑操作，原厂压缩流自检未通过"
            )

        marks = {}

        if args.copy:
            for spec in args.copy:
                source_index, target_index = parse_copy_spec(spec)
                fw.copy_params(
                    args.table,
                    source_index,
                    args.table,
                    target_index,
                )
                marks.setdefault(args.table, set()).add(target_index)
                print(
                    "复制参数：{}[{}] -> {}[{}]".format(
                        args.table,
                        source_index,
                        args.table,
                        target_index,
                    )
                )

        if args.set:
            parameter_length = fw.param_len(args.table)

            for spec in args.set:
                index, mid, params = parse_set_spec(
                    spec,
                    parameter_length,
                )
                old = fw.get_record(args.table, index)

                print()
                print(
                    "设置 {}[{}]：{} -> {}".format(
                        args.table,
                        index,
                        record_mid_text(old),
                        mid if mid is not None else "MID不变",
                    )
                )

                if params is not None:
                    print(
                        "参数：{} -> {}".format(
                            old["params"].hex(),
                            params.hex(),
                        )
                    )

                fw.set_record(
                    args.table,
                    index,
                    mid=mid,
                    params=params,
                )
                marks.setdefault(args.table, set()).add(index)

        if args.delete:
            for index in args.delete:
                old = fw.get_record(args.table, index)
                print()
                print(
                    "删除 {}[{}]：{} -> 整条 FF".format(
                        args.table,
                        index,
                        record_mid_text(old),
                    )
                )
                fw.delete_record(args.table, index)
                marks.setdefault(args.table, set()).add(index)

        if args.add:
            parameter_length = fw.param_len(args.table)

            for spec in args.add:
                mid, params, slot = parse_add_spec(
                    spec,
                    parameter_length,
                )
                index = fw.add_record(
                    args.table,
                    mid,
                    params,
                    slot=slot,
                )
                print()
                print(
                    "新增 {}[{}]：MID={} 参数={}".format(
                        args.table,
                        index,
                        mid,
                        params.hex(),
                    )
                )
                marks.setdefault(args.table, set()).add(index)

        show_physical_table(
            fw,
            args.table,
            hide_empty=args.hide_empty,
            marks=marks.get(args.table, set()),
        )

        return save_edit_result(fw, args)

    except Exception as error:
        print()
        print("操作失败：{}".format(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
