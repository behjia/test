// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtop__pch.h"

Vtop__Syms::Vtop__Syms(VerilatedContext* contextp, const char* namep, Vtop* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup top module instance
    , TOP{this, namep}
{
    // Check resources
    Verilated::stackCheck(112);
    // Setup sub module instances
    TOP__branch_comparator.ctor(this, "branch_comparator");
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-9);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    TOP.__PVT__branch_comparator = &TOP__branch_comparator;
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    TOP__branch_comparator.__Vconfigure(true);
    // Setup scopes
    __Vscopep_TOP = new VerilatedScope{this, "TOP", "TOP", "<null>", 0, VerilatedScope::SCOPE_OTHER};
    __Vscopep_branch_comparator = new VerilatedScope{this, "branch_comparator", "branch_comparator", "branch_comparator", -9, VerilatedScope::SCOPE_MODULE};
    // Set up scope hierarchy
    __Vhier.add(0, __Vscopep_branch_comparator);
    // Setup export functions - final: 0
    // Setup export functions - final: 1
    // Setup public variables
    __Vscopep_TOP->varInsert("branch_taken", &(TOP.branch_taken), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW, 0, 1 ,0,0);
    __Vscopep_TOP->varInsert("branch_type", &(TOP.branch_type), false, VLVT_UINT8, VLVD_IN|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_TOP->varInsert("eq_flag", &(TOP.eq_flag), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_TOP->varInsert("lt_signed", &(TOP.lt_signed), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_TOP->varInsert("lt_unsigned", &(TOP.lt_unsigned), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_TOP->varInsert("operand_a", &(TOP.operand_a), false, VLVT_UINT32, VLVD_IN|VLVF_PUB_RW, 0, 1 ,31,0);
    __Vscopep_TOP->varInsert("operand_b", &(TOP.operand_b), false, VLVT_UINT32, VLVD_IN|VLVF_PUB_RW, 0, 1 ,31,0);
    __Vscopep_branch_comparator->varInsert("BEQ", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BEQ))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("BGE", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BGE))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("BGEU", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BGEU))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("BLT", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BLT))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("BLTU", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BLTU))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("BNE", const_cast<void*>(static_cast<const void*>(&(TOP__branch_comparator.BNE))), true, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("branch_taken", &(TOP__branch_comparator.branch_taken), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW, 0, 1 ,0,0);
    __Vscopep_branch_comparator->varInsert("branch_type", &(TOP__branch_comparator.branch_type), false, VLVT_UINT8, VLVD_IN|VLVF_PUB_RW, 0, 1 ,2,0);
    __Vscopep_branch_comparator->varInsert("eq_flag", &(TOP__branch_comparator.eq_flag), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_branch_comparator->varInsert("lt_signed", &(TOP__branch_comparator.lt_signed), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_branch_comparator->varInsert("lt_unsigned", &(TOP__branch_comparator.lt_unsigned), false, VLVT_UINT8, VLVD_OUT|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,0,0);
    __Vscopep_branch_comparator->varInsert("operand_a", &(TOP__branch_comparator.operand_a), false, VLVT_UINT32, VLVD_IN|VLVF_PUB_RW, 0, 1 ,31,0);
    __Vscopep_branch_comparator->varInsert("operand_b", &(TOP__branch_comparator.operand_b), false, VLVT_UINT32, VLVD_IN|VLVF_PUB_RW, 0, 1 ,31,0);
    __Vscopep_branch_comparator->varInsert("probe_difference", &(TOP__branch_comparator.probe_difference), false, VLVT_UINT64, VLVD_NODIR|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 1 ,32,0);
    __Vscopep_branch_comparator->varInsert("probe_eq_result", &(TOP__branch_comparator.probe_eq_result), false, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 0);
    __Vscopep_branch_comparator->varInsert("probe_lt_signed_result", &(TOP__branch_comparator.probe_lt_signed_result), false, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW, 0, 0);
    __Vscopep_branch_comparator->varInsert("probe_lt_unsigned_result", &(TOP__branch_comparator.probe_lt_unsigned_result), false, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 0);
    __Vscopep_branch_comparator->varInsert("probe_operand_a_sign", &(TOP__branch_comparator.probe_operand_a_sign), false, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 0);
    __Vscopep_branch_comparator->varInsert("probe_operand_b_sign", &(TOP__branch_comparator.probe_operand_b_sign), false, VLVT_UINT8, VLVD_NODIR|VLVF_PUB_RW|VLVF_CONTINUOUSLY, 0, 0);
}

Vtop__Syms::~Vtop__Syms() {
    // Tear down scope hierarchy
    __Vhier.remove(0, __Vscopep_branch_comparator);
    // Clear keys from hierarchy map after values have been removed
    __Vhier.clear();
    if (__Vm_dumping) _traceDumpClose();
    // Tear down scopes
    VL_DO_CLEAR(delete __Vscopep_TOP, __Vscopep_TOP = nullptr);
    VL_DO_CLEAR(delete __Vscopep_branch_comparator, __Vscopep_branch_comparator = nullptr);
    // Tear down sub module instances
    TOP__branch_comparator.dtor();
}

void Vtop__Syms::_traceDump() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    __Vm_dumperp->dump(VL_TIME_Q());
}

void Vtop__Syms::_traceDumpOpen() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    if (VL_UNLIKELY(!__Vm_dumperp)) {
        __Vm_dumperp = new VerilatedVcdC();
        __Vm_modelp->trace(__Vm_dumperp, 0, 0);
        const std::string dumpfile = _vm_contextp__->dumpfileCheck();
        __Vm_dumperp->open(dumpfile.c_str());
        __Vm_dumping = true;
    }
}

void Vtop__Syms::_traceDumpClose() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    __Vm_dumping = false;
    VL_DO_CLEAR(delete __Vm_dumperp, __Vm_dumperp = nullptr);
}
