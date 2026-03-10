module alu_4bit #(
    parameter WIDTH = 4
) (
    input [3:0] a,
    input [3:0] b,
    input [1:0] opcode,
    input clk,
    input rst_n,
    output reg [3:0] result,
    output reg carry_out,
    output reg zero_flag
);

    wire [4:0] add_result;
    wire [3:0] and_result;
    wire [3:0] or_result;
    wire [3:0] sub_result;
    wire sub_borrow;

    assign add_result = a + b;
    assign and_result = a & b;
    assign or_result = a | b;
    assign sub_result = a - b;
    assign sub_borrow = (b > a) ? 1'b1 : 1'b0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 4'b0000;
            carry_out <= 1'b0;
            zero_flag <= 1'b0;
        end else begin
            case (opcode)
                2'b00: begin
                    result <= add_result[3:0];
                    carry_out <= add_result[4];
                    zero_flag <= (add_result[3:0] == 4'b0000) ? 1'b1 : 1'b0;
                end
                2'b01: begin
                    result <= sub_result;
                    carry_out <= sub_borrow;
                    zero_flag <= (sub_result == 4'b0000) ? 1'b1 : 1'b0;
                end
                2'b10: begin
                    result <= and_result;
                    carry_out <= 1'b0;
                    zero_flag <= (and_result == 4'b0000) ? 1'b1 : 1'b0;
                end
                2'b11: begin
                    result <= or_result;
                    carry_out <= 1'b0;
                    zero_flag <= (or_result == 4'b0000) ? 1'b1 : 1'b0;
                end
                default: begin
                    result <= 4'b0000;
                    carry_out <= 1'b0;
                    zero_flag <= 1'b0;
                end
            endcase
        end
    end

endmodule