# Copyright (C) 2010-2015 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import os
import struct

from lib.cuckoo.common.abstracts import Processing
from lib.cuckoo.common.objects import File

PAGE_READONLY = 0x00000002
PAGE_READWRITE = 0x00000004
PAGE_WRITECOPY = 0x00000008
PAGE_EXECUTE = 0x00000010
PAGE_EXECUTE_READ = 0x00000020
PAGE_EXECUTE_READWRITE = 0x00000040
PAGE_EXECUTE_WRITECOPY = 0x00000080

page_access = {
    PAGE_READONLY: "r",
    PAGE_READWRITE: "rw",
    PAGE_WRITECOPY: "rwc",
    PAGE_EXECUTE: "rx",
    PAGE_EXECUTE_READ: "rx",
    PAGE_EXECUTE_READWRITE: "rwx",
    PAGE_EXECUTE_WRITECOPY: "rwxc",
}

class ProcessMemory(Processing):
    """Analyze process memory dumps."""
    def read_dump(self, filepath):
        f = open(filepath, "rb")

        while True:
            buf = f.read(24)
            if not buf:
                break

            row = struct.unpack("QIIII", buf)
            addr, size, state, typ, protect = row

            yield {
                "addr": "0x%08x" % addr,
                "end": "0x%08x" % (addr + size),
                "size": size,
                "type": typ,
                "protect": page_access.get(protect),
                "offset": f.tell(),
            }

            f.seek(size, 1)

    def create_idapy(self, process):
        i = open(process["file"], "rb")
        o = open(process["file"].replace(".dmp", ".py"), "wb")

        print>>o, "from idaapi import add_segm, mem2base, autoMark, AU_CODE"
        print>>o, "from idaapi import set_processor_type, SETPROC_ALL"
        print>>o, "set_processor_type('80386r', SETPROC_ALL)"

        for idx, region in enumerate(process["regions"]):
            i.seek(region["offset"])

            if not region["protect"]:
                section = "unk_%d" % idx
                type_ = "DATA"
            elif "x" in region["protect"]:
                section = "text_%d" % idx
                type_ = "CODE"
            elif "w" in region["protect"]:
                section = "data_%d" % idx
                type_ = "DATA"
            else:
                section = "rdata_%d" % idx
                type_ = "DATA"

            print>>o, "add_segm(0, %s, %s, '%s', '%s')" % (
                region["addr"], region["end"], section, type_
            )
            print>>o, "mem2base('%s'.decode('base64'), %s)" % (
                i.read(region["size"]).encode("base64").replace("\n", ""),
                region["addr"]
            )
            if type_ == "CODE":
                print>>o, "autoMark(%s, AU_CODE)" % region["addr"]

    def run(self):
        """Run analysis.
        @return: structured results.
        """
        self.key = "procmemory"
        results = []

        if os.path.exists(self.pmemory_path):
            for dmp in os.listdir(self.pmemory_path):
                if not dmp.endswith(".dmp"):
                    continue

                dump_path = os.path.join(self.pmemory_path, dmp)
                dump_file = File(dump_path)

                if "-" in os.path.basename(dump_path):
                    pid = int(os.path.basename(dump_path).split("-")[0])
                else:
                    pid = int(os.path.basename(dump_path).split(".")[0])

                proc = dict(
                    file=dump_path, pid=pid,
                    yara=dump_file.get_yara("memory"),
                    urls=list(dump_file.get_urls()),
                    regions=list(self.read_dump(dump_path)),
                )

                if self.options.get("idapro"):
                    self.create_idapy(proc)

                results.append(proc)

        return results
