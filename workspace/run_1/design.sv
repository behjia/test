module alu_4bit #(
    parameter WIDTH = 4
) (
    input logic [3:0] a,
    input logic [3:0] b,
    input logic [1:0] opcode,
    output logic [3:0] result,
    output logic carry_out,
    output logic zero_flag
);

    logic [4:0] add_result;
    logic [3:0] logic_result;

    // Arithmetic operations (addition/subtraction)
    assign add_result = (opcode[0] == 1'b0) ? 
                        (a + b) :           // ADD when opcode[0] = 0
                        (a - b);            // SUB when opcode[0] = 1

    // Logic operations (AND/OR)
    assign logic_result = (opcode[0] == 1'b0) ? 
                          (a & b) :         // AND when opcode[0] = 0
                          (a | b);          // OR when opcode[0] = 1

    // Mux between arithmetic and logic results based on opcode[1]
    assign result = (opcode[1] == 1'b0) ? 
                    add_result[3:0] :      // Arithmetic when opcode[1] = 0
                    logic_result;          // Logic when opcode[1] = 1

    // Carry out only valid for arithmetic operations
    assign carry_out = (opcode[1] == 1'b0) ? add_result[4] : 1'b0;

    // Zero flag for all operations
    assign zero_flag = (result == 4'b0) ? 1'b1 : 1'b0;

endmodule