#ifndef BRANCH_COMPARATOR_DRIVER_H
#define BRANCH_COMPARATOR_DRIVER_H

#include <stdint.h>

// Base address of the IP assigned by Intel Qsys/Platform Designer
#define BRANCH_COMPARATOR_BASE_ADDR 0xFF200000 

// =========================================================================
// AI-GENERATED HARDWARE MEMORY MAP
// =========================================================================
typedef struct {
    
    
    
    volatile uint32_t operand_a; // Offset 0x00
    
    
    
    
    volatile uint32_t operand_b; // Offset 0x00
    
    
    
    
    volatile uint32_t branch_type; // Offset 0x00
    
    
    
    
    
    volatile uint32_t branch_taken; // Offset 0x00 (Read-Only)
    
    
    volatile uint32_t eq_flag; // Offset 0x00 (Read-Only)
    
    
    volatile uint32_t lt_signed; // Offset 0x00 (Read-Only)
    
    
    volatile uint32_t lt_unsigned; // Offset 0x00 (Read-Only)
    
    
} branch_comparator_hw_t;

// Pointer to interact with the hardware block
#define BRANCH_COMPARATOR_HW ((branch_comparator_hw_t *) BRANCH_COMPARATOR_BASE_ADDR)

// Example Usage:
// BRANCH_COMPARATOR_HW->operand_a = 0xFFFF;
// uint32_t result = BRANCH_COMPARATOR_HW->branch_taken;

#endif