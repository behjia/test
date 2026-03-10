# Use Icarus Verilog instead of Verilator
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# The Verilog source file to compile
VERILOG_SOURCES += $(PWD)/design.sv

# The Python testbench file
#COCOTB_TEST_MODULES = test_alu
MODULE = test_alu
TOPLEVEL ?= alu

# Tell Icarus to use SystemVerilog 2012 standards
COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
# # Default to Verilator as the simulation engine
# SIM ?= verilator
# TOPLEVEL_LANG ?= verilog

# # The Verilog source file to compile
# VERILOG_SOURCES += $(PWD)/design.sv

# # The Python testbench file (without the .py extension)
# MODULE = test_alu

# # We inject the TOPLEVEL (module name) dynamically via the terminal
# TOPLEVEL ?= alu

# # Enable Verilator linting and trace generation (for future debugging)
# EXTRA_ARGS += --trace --Wall -Wno-DECLFILENAME -Wno-MULTITOP -Wno-fatal

# include $(shell cocotb-config --makefiles)/Makefile.sim