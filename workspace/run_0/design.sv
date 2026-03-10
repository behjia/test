module alu_4bit #(
  parameter WIDTH = 4
) (
  input wire [3:0] a,
  input wire [3:0] b,
  input wire [1:0] opcode,
  input wire clk,
  input wire rst_n,
  output reg [3:0] result,
  output reg carry_out,
  output reg zero_flag
);

  reg [4:0] temp_result;

  always_comb begin
    case (opcode)
      2'b00: begin
        temp_result = a + b;
        carry_out = temp_result[4];
      end
      2'b01: begin
        temp_result = a - b;
        carry_out = (a < b) ? 1'b1 : 1'b0;
      end
      2'b10: begin
        temp_result = a & b;
        carry_out = 1'b0;
      end
      2'b11: begin
        temp_result = a | b;
        carry_out = 1'b0;
      end
      default: begin
        temp_result = 5'b0;
        carry_out = 1'b0;
      end
    endcase
    
    result = temp_result[3:0];
    zero_flag = (temp_result[3:0] == 4'b0) ? 1'b1 : 1'b0;
  end

endmodule