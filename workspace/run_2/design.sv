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

  logic [4:0] sum_result;
  logic [3:0] and_result;
  logic [3:0] or_result;
  logic [3:0] sub_result;
  logic [4:0] sub_full;

  // Parallel adder for maximum speed
  assign sum_result = a + b;

  // Parallel subtractor
  assign sub_full = a - b;
  assign sub_result = sub_full[3:0];

  // Parallel bitwise operations
  assign and_result = a & b;
  assign or_result = a | b;

  // Mux for opcode selection - optimized for speed
  always_comb begin
    case (opcode)
      2'b00: begin  // ADD
        result = sum_result[3:0];
        carry_out = sum_result[4];
      end
      2'b01: begin  // SUB
        result = sub_result;
        carry_out = sub_full[4];
      end
      2'b10: begin  // AND
        result = and_result;
        carry_out = 1'b0;
      end
      2'b11: begin  // OR
        result = or_result;
        carry_out = 1'b0;
      end
      default: begin
        result = 4'b0;
        carry_out = 1'b0;
      end
    endcase
  end

  // Zero flag generation
  assign zero_flag = (result == 4'b0) ? 1'b1 : 1'b0;

endmodule