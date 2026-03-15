module riscv_instruction_decoder (
    input  logic [31:0] instruction,
    output logic        reg_write,
    output logic        mem_read,
    output logic        mem_write,
    output logic        alu_src,
    output logic        mem_byte,
    output logic        mem_unsigned,
    output logic        is_branch,
    output logic        is_jump,
    output logic [2:0]  alu_op
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    logic [6:0] opcode;
    logic [2:0] funct3;
    logic [6:0] funct7;

    always_comb begin
        // Extract instruction fields
        opcode = instruction[6:0];
        funct3 = instruction[14:12];
        funct7 = instruction[31:25];

        // Default all outputs to 0
        reg_write    = 1'b0;
        mem_read     = 1'b0;
        mem_write    = 1'b0;
        alu_src      = 1'b0;
        mem_byte     = 1'b0;
        mem_unsigned = 1'b0;
        is_branch    = 1'b0;
        is_jump      = 1'b0;
        alu_op       = 3'b000;

        // Decode instructions
        case (opcode)
            7'b0110011: begin // R-type
                if (funct3 == 3'b000 && funct7 == 7'b0000000) begin
                    // add instruction
                    reg_write = 1'b1;
                    alu_src   = 1'b0;
                    alu_op    = 3'b000;
                end
            end

            7'b0010011: begin // I-type arithmetic
                if (funct3 == 3'b000) begin
                    // addi instruction
                    reg_write = 1'b1;
                    alu_src   = 1'b1;
                    alu_op    = 3'b000;
                end
            end

            7'b0110111: begin // U-type
                // lui instruction
                reg_write = 1'b1;
                alu_src   = 1'b1;
                alu_op    = 3'b001;
            end

            7'b0000011: begin // I-type load
                if (funct3 == 3'b010) begin
                    // lw instruction
                    reg_write    = 1'b1;
                    mem_read     = 1'b1;
                    alu_src      = 1'b1;
                    mem_byte     = 1'b0;
                    mem_unsigned = 1'b0;
                    alu_op       = 3'b011;
                end
                else if (funct3 == 3'b100) begin
                    // lbu instruction
                    reg_write    = 1'b1;
                    mem_read     = 1'b1;
                    alu_src      = 1'b1;
                    mem_byte     = 1'b1;
                    mem_unsigned = 1'b1;
                    alu_op       = 3'b011;
                end
            end

            7'b0100011: begin // S-type store
                if (funct3 == 3'b010) begin
                    // sw instruction
                    mem_write    = 1'b1;
                    alu_src      = 1'b1;
                    mem_byte     = 1'b0;
                    mem_unsigned = 1'b0;
                    alu_op       = 3'b011;
                end
                else if (funct3 == 3'b000) begin
                    // sb instruction
                    mem_write    = 1'b1;
                    alu_src      = 1'b1;
                    mem_byte     = 1'b1;
                    mem_unsigned = 1'b0;
                    alu_op       = 3'b011;
                end
            end

            7'b1100111: begin // I-type jalr
                if (funct3 == 3'b000) begin
                    // jalr instruction
                    reg_write = 1'b1;
                    alu_src   = 1'b1;
                    is_jump   = 1'b1;
                    alu_op    = 3'b010;
                end
            end

            default: begin
                // Invalid instruction - all outputs remain 0
            end
        endcase
    end

endmodule