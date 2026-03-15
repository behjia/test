module riscv_imm_gen (
    input  logic [31:0] instr,
    output logic [31:0] imm
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    // Parallel extraction of all possible immediate formats
    logic [31:0] imm_i;
    logic [31:0] imm_s;
    logic [31:0] imm_b;
    logic [31:0] imm_u;
    logic [31:0] imm_j;

    // Opcode extraction for format selection
    logic [6:0] opcode;
    assign opcode = instr[6:0];

    // Truth Table / Logic Map:
    // Opcode[6:0] | Format | Immediate Construction
    // 0010011     | I-type | {{20{instr[31]}}, instr[31:20]}
    // 0000011     | I-type | {{20{instr[31]}}, instr[31:20]} (loads)
    // 1100111     | I-type | {{20{instr[31]}}, instr[31:20]} (jalr)
    // 0100011     | S-type | {{20{instr[31]}}, instr[31:25], instr[11:7]}
    // 1100011     | B-type | {{19{instr[31]}}, instr[31], instr[7], instr[30:25], instr[11:8], 1'b0}
    // 0110111     | U-type | {instr[31:12], 12'b0} (lui)
    // 0010111     | U-type | {instr[31:12], 12'b0} (auipc)
    // 1101111     | J-type | {{11{instr[31]}}, instr[31], instr[19:12], instr[20], instr[30:21], 1'b0}

    always_comb begin
        // I-type: sign_extend(instr[31:20])
        imm_i[11:0]  = instr[31:20];
        imm_i[31:12] = {20{instr[31]}};

        // S-type: sign_extend({instr[31:25], instr[11:7]})
        imm_s[4:0]   = instr[11:7];
        imm_s[11:5]  = instr[31:25];
        imm_s[31:12] = {20{instr[31]}};

        // B-type: sign_extend({instr[31], instr[7], instr[30:25], instr[11:8], 1'b0})
        imm_b[0]     = 1'b0;
        imm_b[4:1]   = instr[11:8];
        imm_b[10:5]  = instr[30:25];
        imm_b[11]    = instr[7];
        imm_b[12]    = instr[31];
        imm_b[31:13] = {19{instr[31]}};

        // U-type: {instr[31:12], 12'b0}
        imm_u[11:0]  = 12'b0;
        imm_u[31:12] = instr[31:12];

        // J-type: sign_extend({instr[31], instr[19:12], instr[20], instr[30:21], 1'b0})
        imm_j[0]     = 1'b0;
        imm_j[10:1]  = instr[30:21];
        imm_j[11]    = instr[20];
        imm_j[19:12] = instr[19:12];
        imm_j[20]    = instr[31];
        imm_j[31:21] = {11{instr[31]}};
    end

    // Final multiplexer based on opcode
    always_comb begin
        case (opcode)
            7'b0010011,  // I-type (alu immediate)
            7'b0000011,  // I-type (loads)
            7'b1100111:  // I-type (jalr)
                imm = imm_i;
            
            7'b0100011:  // S-type (stores)
                imm = imm_s;
            
            7'b1100011:  // B-type (branches)
                imm = imm_b;
            
            7'b0110111,  // U-type (lui)
            7'b0010111:  // U-type (auipc)
                imm = imm_u;
            
            7'b1101111:  // J-type (jal)
                imm = imm_j;
            
            default:
                imm = 32'b0;
        endcase
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_imm_gen);
    end
    `endif
endmodule