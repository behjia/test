// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Tracing implementation internals

#include "verilated_vcd_c.h"
#include "Vtop__Syms.h"


void Vtop___024root__trace_chg_0_sub_0(Vtop___024root* vlSelf, VerilatedVcd::Buffer* bufp);

void Vtop___024root__trace_chg_0(void* voidSelf, VerilatedVcd::Buffer* bufp) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root__trace_chg_0\n"); );
    // Body
    Vtop___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vtop___024root*>(voidSelf);
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    if (VL_UNLIKELY(!vlSymsp->__Vm_activity)) return;
    Vtop___024root__trace_chg_0_sub_0((&vlSymsp->TOP), bufp);
}

void Vtop___024root__trace_chg_0_sub_0(Vtop___024root* vlSelf, VerilatedVcd::Buffer* bufp) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root__trace_chg_0_sub_0\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    uint32_t* const oldp VL_ATTR_UNUSED = bufp->oldp(vlSymsp->__Vm_baseCode + 0);
    bufp->chgIData(oldp+0,(vlSelfRef.operand_a),32);
    bufp->chgIData(oldp+1,(vlSelfRef.operand_b),32);
    bufp->chgCData(oldp+2,(vlSelfRef.branch_type),3);
    bufp->chgBit(oldp+3,(vlSelfRef.branch_taken));
    bufp->chgBit(oldp+4,(vlSelfRef.eq_flag));
    bufp->chgBit(oldp+5,(vlSelfRef.lt_signed));
    bufp->chgBit(oldp+6,(vlSelfRef.lt_unsigned));
    bufp->chgIData(oldp+7,(vlSymsp->TOP__branch_comparator.operand_a),32);
    bufp->chgIData(oldp+8,(vlSymsp->TOP__branch_comparator.operand_b),32);
    bufp->chgCData(oldp+9,(vlSymsp->TOP__branch_comparator.branch_type),3);
    bufp->chgBit(oldp+10,(vlSymsp->TOP__branch_comparator.branch_taken));
    bufp->chgBit(oldp+11,(vlSymsp->TOP__branch_comparator.eq_flag));
    bufp->chgBit(oldp+12,(vlSymsp->TOP__branch_comparator.lt_signed));
    bufp->chgBit(oldp+13,(vlSymsp->TOP__branch_comparator.lt_unsigned));
    bufp->chgBit(oldp+14,(vlSymsp->TOP__branch_comparator.probe_operand_a_sign));
    bufp->chgBit(oldp+15,(vlSymsp->TOP__branch_comparator.probe_operand_b_sign));
    bufp->chgQData(oldp+16,(vlSymsp->TOP__branch_comparator.probe_difference),33);
    bufp->chgBit(oldp+18,(vlSymsp->TOP__branch_comparator.probe_eq_result));
    bufp->chgBit(oldp+19,(vlSymsp->TOP__branch_comparator.probe_lt_signed_result));
    bufp->chgBit(oldp+20,(vlSymsp->TOP__branch_comparator.probe_lt_unsigned_result));
}

void Vtop___024root__trace_cleanup(void* voidSelf, VerilatedVcd* /*unused*/) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtop___024root__trace_cleanup\n"); );
    // Body
    Vtop___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vtop___024root*>(voidSelf);
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    vlSymsp->__Vm_activity = false;
    vlSymsp->TOP.__Vm_traceActivity[0U] = 0U;
}
