import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def alu_basic_test(dut):
    """Test standard addition, subtraction, AND, OR operations of the AI-generated ALU."""
    
    # Define test vectors: (a, b, opcode, expected_result)
    # Assuming standard opcodes: 0=ADD, 1=SUB, 2=AND, 3=OR (Adjust if your LLM chose different mappings)
    test_vectors = [
        (5, 3, 0, 8),   # 5 + 3 = 8
        (5, 3, 1, 2),   # 5 - 3 = 2
        (5, 3, 2, 1),   # 5 & 3 = 1 (0101 & 0011 = 0001)
        (5, 3, 3, 7),   # 5 | 3 = 7 (0101 | 0011 = 0111)
    ]

    for a, b, op, expected in test_vectors:
        # 1. Drive the inputs
        dut.a.value = a
        dut.b.value = b
        dut.opcode.value = op
        
        # 2. Wait 1 nanosecond for the combinational logic to propagate
        await Timer(1, unit="ns")
        
        # 3. Read and assert the output
        result = int(dut.result.value)
        assert result == expected, f"Failed on Opcode {op}: {a} op {b} = {result} (Expected: {expected})"
        
        dut._log.info(f"PASS: {a} op {b} = {result}")