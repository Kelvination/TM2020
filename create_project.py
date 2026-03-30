"""
Create and analyze the TM2020 Ghidra project headlessly.
This imports Trackmania.exe and runs full auto-analysis.

Usage:
  python3 create_project.py
"""

import os
import sys
import time

GHIDRA_INSTALL = "/Users/kelvinnewton/Projects/ghidra/ghidra_12.0.4_PUBLIC"
PROJECT_DIR = "/Users/kelvinnewton/Projects/tm/TM2020"
PROJECT_NAME = "TM2020"
BINARY_PATH = "/Users/kelvinnewton/Projects/tm/TM2020/Trackmania.exe"

os.environ["GHIDRA_INSTALL_DIR"] = GHIDRA_INSTALL

import pyghidra


def main():
    print("Starting PyGhidra...")
    pyghidra.start(install_dir=GHIDRA_INSTALL)

    # Check if project already exists
    gpr_path = os.path.join(PROJECT_DIR, f"{PROJECT_NAME}.gpr")
    if os.path.exists(gpr_path):
        print(f"Project already exists at {gpr_path}")
        print("Opening existing project...")
        project = pyghidra.open_project(PROJECT_DIR, PROJECT_NAME)
        program, consumer = pyghidra.consume_program(project, "/Trackmania.exe")
        print(f"Program: {program.getName()}")
        print(f"Language: {program.getLanguage().getLanguageID()}")
        print(f"Base: {program.getImageBase()}")
        print(f"Functions: {program.getFunctionManager().getFunctionCount()}")
        program.release(consumer)
        project.close()
        return

    print(f"Creating new project: {PROJECT_NAME}")
    print(f"Importing binary: {BINARY_PATH}")
    print("This will take a while for a 43MB binary...")

    start_time = time.time()

    # Import and analyze
    with pyghidra.open_program(BINARY_PATH,
                                project_location=PROJECT_DIR,
                                project_name=PROJECT_NAME) as flat_api:
        program = flat_api.getCurrentProgram()
        print(f"\nImport complete in {time.time() - start_time:.1f}s")
        print(f"Program: {program.getName()}")
        print(f"Language: {program.getLanguage().getLanguageID()}")
        print(f"Compiler: {program.getCompilerSpec().getCompilerSpecID()}")
        print(f"Base address: {program.getImageBase()}")
        print(f"Functions found: {program.getFunctionManager().getFunctionCount()}")

        # Count memory blocks
        mem = program.getMemory()
        print(f"\nMemory blocks:")
        for block in mem.getBlocks():
            perms = ""
            if block.isRead(): perms += "R"
            if block.isWrite(): perms += "W"
            if block.isExecute(): perms += "X"
            init = "init" if block.isInitialized() else "uninit"
            print(f"  {block.getName()}: {block.getStart()}-{block.getEnd()} "
                  f"({block.getSize()} bytes) [{perms}] {init}")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"Project saved to: {gpr_path}")


if __name__ == "__main__":
    main()
