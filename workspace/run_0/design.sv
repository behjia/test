module alu_4bit (
  input  logic [3:0] operand_a,
  input  logic [3:0] operand_b,
  input  logic [1:0] opcode,
  output logic [3:0] result
);

  always_comb begin
    case (opcode)
      2'b00: result = operand_a + operand_b;
      2'b01: result = operand_a - operand_b;
      2'b10: result = operand_a & operand_b;
      2'b11: result = operand_a | operand_b;
      default: result = 4'b0000;
    endcase
  end

endmodule