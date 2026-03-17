// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtop.h for the primary calling header

#ifndef VERILATED_VTOP_BRANCH_COMPARATOR_H_
#define VERILATED_VTOP_BRANCH_COMPARATOR_H_  // guard

#include "verilated.h"


class Vtop__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtop_branch_comparator final {
  public:

    // DESIGN SPECIFIC STATE
    CData/*2:0*/ branch_type;
    CData/*0:0*/ branch_taken;
    CData/*0:0*/ eq_flag;
    CData/*0:0*/ lt_signed;
    CData/*0:0*/ lt_unsigned;
    CData/*0:0*/ probe_operand_a_sign;
    CData/*0:0*/ probe_operand_b_sign;
    CData/*0:0*/ probe_eq_result;
    CData/*0:0*/ probe_lt_signed_result;
    CData/*0:0*/ probe_lt_unsigned_result;
    IData/*31:0*/ operand_a;
    IData/*31:0*/ operand_b;
    QData/*32:0*/ probe_difference;

    // INTERNAL VARIABLES
    Vtop__Syms* vlSymsp;
    const char* vlNamep;

    // PARAMETERS
    static constexpr CData/*2:0*/ BEQ = 0U;
    static constexpr CData/*2:0*/ BNE = 1U;
    static constexpr CData/*2:0*/ BLT = 4U;
    static constexpr CData/*2:0*/ BGE = 5U;
    static constexpr CData/*2:0*/ BLTU = 6U;
    static constexpr CData/*2:0*/ BGEU = 7U;

    // CONSTRUCTORS
    Vtop_branch_comparator();
    ~Vtop_branch_comparator();
    void ctor(Vtop__Syms* symsp, const char* namep);
    void dtor();
    VL_UNCOPYABLE(Vtop_branch_comparator);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
