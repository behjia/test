// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtop.h for the primary calling header

#include "Vtop__pch.h"

VL_ATTR_COLD void Vtop_branch_comparator___eval_initial__TOP__branch_comparator(Vtop_branch_comparator* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+      Vtop_branch_comparator___eval_initial__TOP__branch_comparator\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSymsp->_vm_contextp__->dumpfile("sim_build/dump.vcd"s);
    vlSymsp->_traceDumpOpen();
}

VL_ATTR_COLD void Vtop_branch_comparator___stl_sequent__TOP__branch_comparator__0(Vtop_branch_comparator* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+      Vtop_branch_comparator___stl_sequent__TOP__branch_comparator__0\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.probe_operand_b_sign = (1U & VL_BITSEL_IIII(32, vlSelfRef.operand_b, 0x1fU));
    vlSelfRef.probe_eq_result = (vlSelfRef.operand_a 
                                 == vlSelfRef.operand_b);
    vlSelfRef.probe_operand_a_sign = (1U & VL_BITSEL_IIII(32, vlSelfRef.operand_a, 0x1fU));
    vlSelfRef.probe_difference = (0x00000001ffffffffULL 
                                  & (VL_EXTEND_QI(33,32, vlSelfRef.operand_a) 
                                     - VL_EXTEND_QI(33,32, vlSelfRef.operand_b)));
    vlSelfRef.eq_flag = vlSelfRef.probe_eq_result;
    vlSelfRef.probe_lt_unsigned_result = (1U & VL_BITSEL_IQII(33, vlSelfRef.probe_difference, 0x20U));
    vlSelfRef.probe_lt_signed_result = (1U & (((IData)(vlSelfRef.probe_operand_a_sign) 
                                               != (IData)(vlSelfRef.probe_operand_b_sign))
                                               ? (IData)(vlSelfRef.probe_operand_a_sign)
                                               : VL_BITSEL_IQII(33, vlSelfRef.probe_difference, 0x20U)));
    vlSelfRef.lt_unsigned = vlSelfRef.probe_lt_unsigned_result;
    vlSelfRef.lt_signed = vlSelfRef.probe_lt_signed_result;
    vlSelfRef.branch_taken = (1U & ((0U == (IData)(vlSelfRef.branch_type))
                                     ? (IData)(vlSelfRef.probe_eq_result)
                                     : ((1U == (IData)(vlSelfRef.branch_type))
                                         ? (~ (IData)(vlSelfRef.probe_eq_result))
                                         : ((4U == (IData)(vlSelfRef.branch_type))
                                             ? (IData)(vlSelfRef.probe_lt_signed_result)
                                             : ((5U 
                                                 == (IData)(vlSelfRef.branch_type))
                                                 ? 
                                                (~ (IData)(vlSelfRef.probe_lt_signed_result))
                                                 : 
                                                ((6U 
                                                  == (IData)(vlSelfRef.branch_type))
                                                  ? (IData)(vlSelfRef.probe_lt_unsigned_result)
                                                  : 
                                                 ((7U 
                                                   == (IData)(vlSelfRef.branch_type)) 
                                                  && (1U 
                                                      & (~ (IData)(vlSelfRef.probe_lt_unsigned_result))))))))));
}

VL_ATTR_COLD void Vtop_branch_comparator___ctor_var_reset(Vtop_branch_comparator* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+      Vtop_branch_comparator___ctor_var_reset\n"); );
    Vtop__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->operand_a = 0;
    vlSelf->operand_b = 0;
    vlSelf->branch_type = 0;
    vlSelf->branch_taken = 0;
    vlSelf->eq_flag = 0;
    vlSelf->lt_signed = 0;
    vlSelf->lt_unsigned = 0;
    vlSelf->probe_operand_a_sign = 0;
    vlSelf->probe_operand_b_sign = 0;
    vlSelf->probe_difference = 0;
    vlSelf->probe_eq_result = 0;
    vlSelf->probe_lt_signed_result = 0;
    vlSelf->probe_lt_unsigned_result = 0;
}
