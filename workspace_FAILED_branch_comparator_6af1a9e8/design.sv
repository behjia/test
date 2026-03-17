module branch_comparator (

    input logic [31:0] operand_a,

    input logic [31:0] operand_b,

    input logic [2:0] branch_type,


    output logic [0:0] branch_taken,

    output logic [0:0] eq_flag,

    output logic [0:0] lt_signed,

    output logic [0:0] lt_unsigned

);

// --- AI GENERATED INTERNAL LOGIC ---
// Branch type encoding (RISC-V funct3 for branch instructions)
localparam [2:0] BEQ  = 3'b000;
localparam [2:0] BNE  = 3'b001;
localparam [2:0] BLT  = 3'b100;
localparam [2:0] BGE  = 3'b101;
localparam [2:0] BLTU = 3'b110;
localparam [2:0] BGEU = 3'b111;

// Internal signals (must be logic for always_comb)
logic probe_operand_a_sign;
logic probe_operand_b_sign;
logic [32:0] probe_difference;
logic probe_eq_result;
logic probe_lt_signed_result;
logic probe_lt_unsigned_result;

// Extract sign bits
assign probe_operand_a_sign = operand_a[31];
assign probe_operand_b_sign = operand_b[31];

// Compute difference for unsigned comparison (33-bit to capture borrow)
assign probe_difference = {1'b0, operand_a} - {1'b0, operand_b};

// Equality comparison
assign probe_eq_result = (operand_a == operand_b);
assign eq_flag = probe_eq_result;

// Signed less-than comparison
always_comb begin
    if (probe_operand_a_sign != probe_operand_b_sign) begin
        // Different signs: negative < positive
        probe_lt_signed_result = probe_operand_a_sign;
    end else begin
        // Same signs: compare magnitudes using unsigned subtraction
        probe_lt_signed_result = probe_difference[32];
    end
end
assign lt_signed = probe_lt_signed_result;

// Unsigned less-than comparison
assign probe_lt_unsigned_result = probe_difference[32];
assign lt_unsigned = probe_lt_unsigned_result;

// Branch decision logic
always_comb begin
    case (branch_type)
        BEQ:  branch_taken = probe_eq_result;
        BNE:  branch_taken = ~probe_eq_result;
        BLT:  branch_taken = probe_lt_signed_result;
        BGE:  branch_taken = ~probe_lt_signed_result;
        BLTU: branch_taken = probe_lt_unsigned_result;
        BGEU: branch_taken = ~probe_lt_unsigned_result;
        default: branch_taken = 1'b0;
    endcase
end
// -----------------------------------


`ifndef SYNTHESIS
initial begin
    $dumpfile("sim_build/dump.vcd");
    $dumpvars(0, branch_comparator);
end
`endif

endmodule

