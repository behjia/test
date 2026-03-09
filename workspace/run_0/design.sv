module alu_4bit #(
  parameter WIDTH = 4
) (
  input  [3:0] a,
  input  [3:0] b,
  input  [1:0] opcode,
  output [3:0] result,
  output [0:0] carry_out,
  output [0:0] zero_flag
);

  logic [4:0] temp_result;
  logic [3:0] alu_result;

  always_comb begin
    case (opcode)
      2'b00: begin
        // Addition
        temp_result = {1'b0, a} + {1'b0, b};
        alu_result = temp_result[3:0];
      end
      2'b01: begin
        // Subtraction
        temp_result = {1'b0, a} - {1'b0, b};
        alu_result = temp_result[3:0];
      end
      2'b10: begin
        // AND
        temp_result = {1'b0, (a & b)};
        alu_result = temp_result[3:0];
      end
      2'b11: begin
        // OR
        temp_result = {1'b0, (a | b)};
        alu_result = temp_result[3:0];
      end
      default: begin
        temp_result = 5'b0;
        alu_result = 4'b0;
      end
    endcase
  end

  assign result = alu_result;
  assign carry_out = temp_result[4];
  assign zero_flag = (alu_result == 4'b0) ? 1'b1 : 1'b0;

endmodule