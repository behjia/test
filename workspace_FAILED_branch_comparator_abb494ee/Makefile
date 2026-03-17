MAKEFLAGS += -s
SIM ?= verilator
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/*.sv

# MODERN COCOTB 2.0 SYNTAX
COCOTB_TEST_MODULES = test_design
export COCOTB_TEST_MODULES

# We pass TOPLEVEL from the Python subprocess
TOPLEVEL ?= alu

# Disable C++ optimization for lightning-fast compilation during debug loops
COMPILE_ARGS += -O0
# Suppress ALL linting warnings (Latches, Widths, Unused) so AI code compiles
EXTRA_ARGS += --timing --trace -Wno-fatal -Wno-lint -Wno-style -Wno-SYMRSVDWORD -O0 --x-assign fast --x-initial fast --noassert

include $(shell cocotb-config --makefiles)/Makefile.sim

# # Either one
# SIM ?= icarus
# TOPLEVEL_LANG ?= verilog

# VERILOG_SOURCES += $(PWD)/design.sv

# MODULE = test_alu
# export MODULE

# TOPLEVEL ?= alu

# # Simulator-specific flags
# ifeq ($(SIM),verilator)
#     EXTRA_ARGS += --timing --trace -Wno-fatal -Wno-lint -Wno-style -Wno-SYMRSVDWORD
# endif

# include $(shell cocotb-config --makefiles)/Makefile.sim

# # Use Icarus Verilog instead of Verilator
# SIM ?= icarus
# TOPLEVEL_LANG ?= verilog

# # The Verilog source file to compile
# VERILOG_SOURCES += $(PWD)/design.sv

# # The Python testbench file
# #COCOTB_TEST_MODULES = test_alu
# MODULE = test_alu
# TOPLEVEL ?= alu

# # Tell Icarus to use SystemVerilog 2012 standards
# COMPILE_ARGS += -g2012

# include $(shell cocotb-config --makefiles)/Makefile.sim
