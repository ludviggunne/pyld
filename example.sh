#!/usr/bin/env python3

import sys
from pyld import *

main = Target("main", TargetType.EXECUTABLE)
main.add_include_directories(["example/lib"])
main.add_source_files(["example/main.c", "example/other.c"])

lib = Target("lib", TargetType.STATIC_LIB)
lib.add_source_files(["example/lib/lib.c"])

m = ExtDep("m", ExtDepType.SYSTEM_LIB)

main.add_dependencies(["lib", "m"])

if len(sys.argv) == 1:
    main.build()
else:
    match sys.argv[1]:
        case "clean":
            main.clean()

        case "run":
            main.build()
            main.run()
            
        case "force":
            main.build(force = True)

        case _:
            print(f"Unknown sub-command {sys.argv[1]}")