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

    // Extract instruction fields
    logic [6:0] opcode;
    logic [2:0] funct3;
    logic [6:0] funct7;
    
    assign opcode = instruction[6:0];
    assign funct3 = instruction[14:12];
    assign funct7 = instruction[31:25];

    // ROM address and control signals
    logic [16:0] rom_addr;
    logic [11:0] control_word;
    
    // ROM address: {opcode[6:0], funct3[2:0], funct7[6:0]}
    // For efficiency, we use a subset: {opcode[6:0], funct3[2:0], funct7[5]} = 11 bits
    assign rom_addr = {opcode, funct3, funct7[5]};
    
    // Control word format: {reg_write, mem_read, mem_write, alu_src, mem_byte, mem_unsigned, is_branch, is_jump, alu_op[2:0]}
    always_comb begin
        // Default: all zeros (invalid instruction)
        control_word = 12'b0;
        
        case (rom_addr)
            // add: opcode=0x33, funct3=0x0, funct7[5]=0
            11'b0110011_000_0: control_word = 12'b1_0_0_0_0_0_0_0_000; // reg_write=1, alu_op=0
            
            // addi: opcode=0x13, funct3=0x0
            11'b0010011_000_0,
            11'b0010011_000_1: control_word = 12'b1_0_0_1_0_0_0_0_000; // reg_write=1, alu_src=1, alu_op=0
            
            // lui: opcode=0x37
            11'b0110111_000_0,
            11'b0110111_000_1,
            11'b0110111_001_0,
            11'b0110111_001_1,
            11'b0110111_010_0,
            11'b0110111_010_1,
            11'b0110111_011_0,
            11'b0110111_011_1,
            11'b0110111_100_0,
            11'b0110111_100_1,
            11'b0110111_101_0,
            11'b0110111_101_1,
            11'b0110111_110_0,
            11'b0110111_110_1,
            11'b0110111_111_0,
            11'b0110111_111_1: control_word = 12'b1_0_0_1_0_0_0_0_001; // reg_write=1, alu_src=1, alu_op=1
            
            // lw: opcode=0x03, funct3=0x2
            11'b0000011_010_0,
            11'b0000011_010_1: control_word = 12'b1_1_0_1_0_0_0_0_011; // reg_write=1, mem_read=1, alu_src=1, alu_op=3
            
            // lbu: opcode=0x03, funct3=0x4
            11'b0000011_100_0,
            11'b0000011_100_1: control_word = 12'b1_1_0_1_1_1_0_0_011; // reg_write=1, mem_read=1, alu_src=1, mem_byte=1, mem_unsigned=1, alu_op=3
            
            // sw: opcode=0x23, funct3=0x2
            11'b0100011_010_0,
            11'b0100011_010_1: control_word = 12'b0_0_1_1_0_0_0_0_011; // mem_write=1, alu_src=1, alu_op=3
            
            // sb: opcode=0x23, funct3=0x0
            11'b0100011_000_0,
            11'b0100011_000_1: control_word = 12'b0_0_1_1_1_0_0_0_011; // mem_write=1, alu_src=1, mem_byte=1, alu_op=3
            
            // jalr: opcode=0x67, funct3=0x0
            11'b1100111_000_0,
            11'b1100111_000_1: control_word = 12'b1_0_0_1_0_0_0_1_010; // reg_write=1, alu_src=1, is_jump=1, alu_op=2
            
            default: control_word = 12'b0; // Invalid instruction
        endcase
    end
    
    // Unpack control word
    assign {reg_write, mem_read, mem_write, alu_src, mem_byte, mem_unsigned, is_branch, is_jump, alu_op} = control_word;

endmodule