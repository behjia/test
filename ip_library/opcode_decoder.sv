module riscv_opcode_decoder (
    input  logic [6:0] opcode,
    output logic       is_r_type,
    output logic       is_i_type_alu,
    output logic       is_i_type_load,
    output logic       is_s_type,
    output logic       is_b_type,
    output logic       is_u_type_lui,
    output logic       is_j_type_jal,
    output logic       is_i_type_jalr
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    // RISC-V Opcode Definitions (7-bit)
    localparam logic [6:0] OPCODE_R_TYPE      = 7'b0110011;  // R-type (add, etc.)
    localparam logic [6:0] OPCODE_I_ALU       = 7'b0010011;  // I-type ALU (addi, etc.)
    localparam logic [6:0] OPCODE_LOAD        = 7'b0000011;  // I-type Load (lw, lbu)
    localparam logic [6:0] OPCODE_STORE       = 7'b0100011;  // S-type Store (sw, sb)
    localparam logic [6:0] OPCODE_BRANCH      = 7'b1100011;  // B-type Branch
    localparam logic [6:0] OPCODE_LUI         = 7'b0110111;  // U-type LUI
    localparam logic [6:0] OPCODE_JAL         = 7'b1101111;  // J-type JAL
    localparam logic [6:0] OPCODE_JALR        = 7'b1100111;  // I-type JALR

    // Internal probes for monitoring
    logic probe_opcode_match_r;
    logic probe_opcode_match_i_alu;
    logic probe_opcode_match_load;
    logic probe_opcode_match_store;
    logic probe_opcode_valid;

    // ROM-based lookup table structure
    // Truth Table:
    // opcode[6:0] | is_r | is_i_alu | is_i_load | is_s | is_b | is_u_lui | is_j_jal | is_i_jalr
    // 0110011     |  1   |    0     |     0     |  0   |  0   |    0     |    0     |     0
    // 0010011     |  0   |    1     |     0     |  0   |  0   |    0     |    0     |     0
    // 0000011     |  0   |    0     |     1     |  0   |  0   |    0     |    0     |     0
    // 0100011     |  0   |    0     |     0     |  1   |  0   |    0     |    0     |     0
    // 1100011     |  0   |    0     |     0     |  0   |  1   |    0     |    0     |     0
    // 0110111     |  0   |    0     |     0     |  0   |  0   |    1     |    0     |     0
    // 1101111     |  0   |    0     |     0     |  0   |  0   |    0     |    1     |     0
    // 1100111     |  0   |    0     |     0     |  0   |  0   |    0     |    0     |     1
    // default     |  0   |    0     |     0     |  0   |  0   |    0     |    0     |     0

    always_comb begin
        // Default all outputs to 0
        is_r_type      = 1'b0;
        is_i_type_alu  = 1'b0;
        is_i_type_load = 1'b0;
        is_s_type      = 1'b0;
        is_b_type      = 1'b0;
        is_u_type_lui  = 1'b0;
        is_j_type_jal  = 1'b0;
        is_i_type_jalr = 1'b0;

        probe_opcode_match_r     = 1'b0;
        probe_opcode_match_i_alu = 1'b0;
        probe_opcode_match_load  = 1'b0;
        probe_opcode_match_store = 1'b0;
        probe_opcode_valid       = 1'b0;

        // ROM lookup: Use opcode as index into decode table
        case (opcode)
            OPCODE_R_TYPE: begin
                is_r_type            = 1'b1;
                probe_opcode_match_r = 1'b1;
                probe_opcode_valid   = 1'b1;
            end

            OPCODE_I_ALU: begin
                is_i_type_alu            = 1'b1;
                probe_opcode_match_i_alu = 1'b1;
                probe_opcode_valid       = 1'b1;
            end

            OPCODE_LOAD: begin
                is_i_type_load         = 1'b1;
                probe_opcode_match_load = 1'b1;
                probe_opcode_valid      = 1'b1;
            end

            OPCODE_STORE: begin
                is_s_type               = 1'b1;
                probe_opcode_match_store = 1'b1;
                probe_opcode_valid       = 1'b1;
            end

            OPCODE_BRANCH: begin
                is_b_type          = 1'b1;
                probe_opcode_valid = 1'b1;
            end

            OPCODE_LUI: begin
                is_u_type_lui      = 1'b1;
                probe_opcode_valid = 1'b1;
            end

            OPCODE_JAL: begin
                is_j_type_jal      = 1'b1;
                probe_opcode_valid = 1'b1;
            end

            OPCODE_JALR: begin
                is_i_type_jalr     = 1'b1;
                probe_opcode_valid = 1'b1;
            end

            default: begin
                // All outputs remain 0 (invalid opcode)
                probe_opcode_valid = 1'b0;
            end
        endcase
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_opcode_decoder);
    end
    `endif
endmodule