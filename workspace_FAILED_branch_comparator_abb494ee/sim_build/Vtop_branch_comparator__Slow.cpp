// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtop.h for the primary calling header

#include "Vtop__pch.h"

// Parameter definitions for Vtop_branch_comparator
constexpr CData/*2:0*/ Vtop_branch_comparator::BEQ;
constexpr CData/*2:0*/ Vtop_branch_comparator::BNE;
constexpr CData/*2:0*/ Vtop_branch_comparator::BLT;
constexpr CData/*2:0*/ Vtop_branch_comparator::BGE;
constexpr CData/*2:0*/ Vtop_branch_comparator::BLTU;
constexpr CData/*2:0*/ Vtop_branch_comparator::BGEU;


void Vtop_branch_comparator___ctor_var_reset(Vtop_branch_comparator* vlSelf);

Vtop_branch_comparator::Vtop_branch_comparator() = default;
Vtop_branch_comparator::~Vtop_branch_comparator() = default;

void Vtop_branch_comparator::ctor(Vtop__Syms* symsp, const char* namep) {
    vlSymsp = symsp;
    vlNamep = strdup(Verilated::catName(vlSymsp->name(), namep));
    // Reset structure values
    Vtop_branch_comparator___ctor_var_reset(this);
}

void Vtop_branch_comparator::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

void Vtop_branch_comparator::dtor() {
    VL_DO_DANGLING(std::free(const_cast<char*>(vlNamep)), vlNamep);
}
