module alu_4bit #(
  parameter WIDTH = 4
) (
  input  logic [3:0] a,
  input  logic [3:0] b,
  input  logic [1:0] opcode,
  output logic [3:0] result,
  output logic       carry_out,
  output logic       zero_flag
);

  logic [4:0] add_result;
  logic [3:0] logic_result;

  // Adder/Subtractor (opcode[1] determines add vs subtract)
  assign add_result = opcode[1] ? (a - b) : (a + b);
  
  // Logic operations
  assign logic_result = opcode[0] ? (a | b) : (a & b);

  // Mux between arithmetic and logic results
  assign result = opcode[1] ? logic_result : add_result[3:0];
  
  // Carry out from addition/subtraction
  assign carry_out = opcode[1] ? 1'b0 : add_result[4];
  
  // Zero flag
  assign zero_flag = (result == 4'b0) ? 1'b1 : 1'b0;

endmodule