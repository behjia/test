module riscv_imm_gen (
    input  logic [31:0] instruction,
    output logic [31:0] imm_out
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    // Opcode field extraction
    logic [6:0] opcode;
    assign opcode = instruction[6:0];

    // Parallel extraction of all immediate types
    logic [31:0] imm_I;
    logic [31:0] imm_S;
    logic [31:0] imm_B;
    logic [31:0] imm_U;
    logic [31:0] imm_J;

    // I-type: imm[11:0] = inst[31:20]
    // Sign-extend from bit 31
    assign imm_I = {{20{instruction[31]}}, instruction[31:20]};

    // S-type: imm[11:5] = inst[31:25], imm[4:0] = inst[11:7]
    // Sign-extend from bit 31
    assign imm_S = {{20{instruction[31]}}, instruction[31:25], instruction[11:7]};

    // B-type: imm[12|10:5|4:1|11] = inst[31|30:25|11:8|7]
    // Sign-extend from bit 31
    assign imm_B = {{19{instruction[31]}}, instruction[31], instruction[7], instruction[30:25], instruction[11:8], 1'b0};

    // U-type: imm[31:12] = inst[31:12], imm[11:0] = 0
    assign imm_U = {instruction[31:12], 12'b0};

    // J-type: imm[20|10:1|11|19:12] = inst[31|30:21|20|19:12]
    // Sign-extend from bit 31
    assign imm_J = {{11{instruction[31]}}, instruction[31], instruction[19:12], instruction[20], instruction[30:21], 1'b0};

    // Opcode-based multiplexer
    // Truth Table for RISC-V Immediate Types:
    // Opcode      Type    Immediate Format
    // 0010011     I-type  imm[11:0]
    // 0000011     I-type  imm[11:0] (loads)
    // 1100111     I-type  imm[11:0] (JALR)
    // 0100011     S-type  imm[11:5|4:0]
    // 1100011     B-type  imm[12|10:5|4:1|11]
    // 0110111     U-type  imm[31:12] (LUI)
    // 0010111     U-type  imm[31:12] (AUIPC)
    // 1101111     J-type  imm[20|10:1|11|19:12] (JAL)

    always_comb begin
        case (opcode)
            7'b0010011: imm_out = imm_I; // I-type (ALU immediate)
            7'b0000011: imm_out = imm_I; // I-type (load)
            7'b1100111: imm_out = imm_I; // I-type (JALR)
            7'b0100011: imm_out = imm_S; // S-type (store)
            7'b1100011: imm_out = imm_B; // B-type (branch)
            7'b0110111: imm_out = imm_U; // U-type (LUI)
            7'b0010111: imm_out = imm_U; // U-type (AUIPC)
            7'b1101111: imm_out = imm_J; // J-type (JAL)
            default:    imm_out = 32'b0;
        endcase
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_imm_gen);
    end
    `endif
endmodule