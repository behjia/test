module alu_4bit #(
  parameter WIDTH = 4
) (
  input  logic [3:0] a,
  input  logic [3:0] b,
  input  logic [1:0] opcode,
  input  logic       clk,
  input  logic       rst_n,
  output logic [3:0] result,
  output logic       carry_out,
  output logic       zero_flag
);

  logic [4:0] add_result;
  logic [3:0] alu_result;

  // Combinatorial ALU operations
  always_comb begin
    case (opcode)
      2'b00: begin
        // Addition with carry detection
        add_result = {1'b0, a} + {1'b0, b};
        alu_result = add_result[3:0];
        carry_out = add_result[4];
      end
      2'b01: begin
        // Subtraction with borrow detection
        add_result = {1'b0, a} - {1'b0, b};
        alu_result = add_result[3:0];
        carry_out = add_result[4];
      end
      2'b10: begin
        // Bitwise AND
        alu_result = a & b;
        carry_out = 1'b0;
      end
      2'b11: begin
        // Bitwise OR
        alu_result = a | b;
        carry_out = 1'b0;
      end
      default: begin
        alu_result = 4'b0000;
        carry_out = 1'b0;
      end
    endcase
  end

  // Zero flag generation
  assign zero_flag = (alu_result == 4'b0000) ? 1'b1 : 1'b0;

  // Output assignment
  assign result = alu_result;

endmodule