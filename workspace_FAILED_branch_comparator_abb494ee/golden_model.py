import random

# AI-Generated Data Dictionary
TRUTH_TABLE = {"truth_table":{"beq_equal":{"inputs":{"operand_a":42,"operand_b":42,"branch_type":0},"outputs":{"branch_taken":1,"eq_flag":1,"lt_signed":0,"lt_unsigned":0}},"beq_not_equal":{"inputs":{"operand_a":42,"operand_b":100,"branch_type":0},"outputs":{"branch_taken":0,"eq_flag":0,"lt_signed":1,"lt_unsigned":1}},"bne_not_equal":{"inputs":{"operand_a":42,"operand_b":100,"branch_type":1},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":1,"lt_unsigned":1}},"bne_equal":{"inputs":{"operand_a":42,"operand_b":42,"branch_type":1},"outputs":{"branch_taken":0,"eq_flag":1,"lt_signed":0,"lt_unsigned":0}},"blt_signed_less":{"inputs":{"operand_a":-10,"operand_b":10,"branch_type":2},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":1,"lt_unsigned":0}},"blt_signed_greater":{"inputs":{"operand_a":10,"operand_b":-10,"branch_type":2},"outputs":{"branch_taken":0,"eq_flag":0,"lt_signed":0,"lt_unsigned":1}},"bge_signed_greater_equal":{"inputs":{"operand_a":10,"operand_b":5,"branch_type":3},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":0,"lt_unsigned":0}},"bge_signed_less":{"inputs":{"operand_a":5,"operand_b":10,"branch_type":3},"outputs":{"branch_taken":0,"eq_flag":0,"lt_signed":1,"lt_unsigned":1}},"bltu_unsigned_less":{"inputs":{"operand_a":5,"operand_b":10,"branch_type":4},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":1,"lt_unsigned":1}},"bltu_unsigned_greater":{"inputs":{"operand_a":10,"operand_b":5,"branch_type":4},"outputs":{"branch_taken":0,"eq_flag":0,"lt_signed":0,"lt_unsigned":0}},"bgeu_unsigned_greater_equal":{"inputs":{"operand_a":10,"operand_b":5,"branch_type":5},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":0,"lt_unsigned":0}},"bgeu_unsigned_less":{"inputs":{"operand_a":5,"operand_b":10,"branch_type":5},"outputs":{"branch_taken":0,"eq_flag":0,"lt_signed":1,"lt_unsigned":1}},"zero_operands":{"inputs":{"operand_a":0,"operand_b":0,"branch_type":0},"outputs":{"branch_taken":1,"eq_flag":1,"lt_signed":0,"lt_unsigned":0}},"max_unsigned_vs_zero":{"inputs":{"operand_a":4294967295,"operand_b":0,"branch_type":5},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":0,"lt_unsigned":0}},"negative_signed_comparison":{"inputs":{"operand_a":2147483648,"operand_b":1,"branch_type":2},"outputs":{"branch_taken":1,"eq_flag":0,"lt_signed":1,"lt_unsigned":0}}}}

def generate_test_vectors():
    test_vectors = []
    # Generate edge cases from the Truth Table
    table_data = TRUTH_TABLE.get("truth_table", TRUTH_TABLE)
    for key, data in table_data.items():
        # Inject the primary input (e.g., opcode or instruction)
        vec = {k: v for k, v in data.get("inputs", {}).items()}
        # Fill remaining ports with random noise to ensure robustness
        # (Assuming your verifier.py passes 'input_ports' to this template)
        for port in ['operand_a', 'operand_b', 'branch_type']:
            if port not in vec:
                vec[port] = random.randint(0, (1 << {'operand_a': 32, 'operand_b': 32, 'branch_type': 3}.get(port, 1)) - 1)
        test_vectors.append(vec)
    
    # Pad with random vectors up to (len(TRUTH_TABLE) + 5)
    while len(test_vectors) < (len(TRUTH_TABLE) + 5):
        vec = {}
        for port in ['operand_a', 'operand_b', 'branch_type']:
            vec[port] = random.randint(0, (1 << {'operand_a': 32, 'operand_b': 32, 'branch_type': 3}.get(port, 1)) - 1)
        test_vectors.append(vec)
        
    return test_vectors

def golden_model(model_state, inputs):
    expected_output = {}
    
    # 1. Try to match the inputs to our Truth Table
    table_data = TRUTH_TABLE.get("truth_table", TRUTH_TABLE)
    for key, data in table_data.items():
        match = True
        for ink, inv in data.get("inputs", {}).items():
            if inputs.get(ink) != inv:
                match = False
                break
        if match:
            expected_output = data.get("outputs", {})
            return model_state, expected_output
            
    # 2. Fallback Logic
    # If no exact match in the TRUTH_TABLE, calculate the result programmatically.
    
    # --- BRANCH COMPARATOR FALLBACK MATH ---
    op_a = inputs.get('operand_a', 0)
    op_b = inputs.get('operand_b', 0)
    
    # Handle Python's negative number representation for signed comparison
    op_a_signed = op_a - (1<<32) if op_a & (1<<31) else op_a
    op_b_signed = op_b - (1<<32) if op_b & (1<<31) else op_b

    eq = (op_a == op_b)
    lt_s = op_a_signed < op_b_signed
    lt_u = op_a < op_b
    
    branch_type = inputs.get('branch_type', 0)
    taken = 0
    if branch_type == 0 and eq: taken = 1     # BEQ
    elif branch_type == 1 and not eq: taken = 1 # BNE
    elif branch_type == 2 and lt_s: taken = 1 # BLT
    elif branch_type == 3 and not lt_s: taken = 1 # BGE
    elif branch_type == 4 and lt_u: taken = 1 # BLTU
    elif branch_type == 5 and not lt_u: taken = 1 # BGEU

    expected_output['branch_taken'] = taken
    expected_output['eq_flag'] = 1 if eq else 0
    expected_output['lt_signed'] = 1 if lt_s else 0
    expected_output['lt_unsigned'] = 1 if lt_u else 0
    
    return model_state, expected_output