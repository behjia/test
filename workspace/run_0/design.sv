module alu_4bit #(
    parameter WIDTH = 4
) (
    input  [WIDTH-1:0] a,
    input  [WIDTH-1:0] b,
    input  [1:0]       opcode,
    output [WIDTH-1:0] result,
    output             carry_out,
    output             zero_flag
);

    logic [WIDTH:0]   temp_result;
    logic [WIDTH-1:0] final_result;

    always_comb begin
        case (opcode)
            2'b00: begin
                // Addition
                temp_result = a + b;
                final_result = temp_result[WIDTH-1:0];
            end
            2'b01: begin
                // Subtraction
                temp_result = a - b;
                final_result = temp_result[WIDTH-1:0];
            end
            2'b10: begin
                // AND
                temp_result = a & b;
                final_result = temp_result[WIDTH-1:0];
            end
            2'b11: begin
                // OR
                temp_result = a | b;
                final_result = temp_result[WIDTH-1:0];
            end
            default: begin
                temp_result = '0;
                final_result = '0;
            end
        endcase
    end

    assign result = final_result;
    assign carry_out = temp_result[WIDTH];
    assign zero_flag = (final_result == '0) ? 1'b1 : 1'b0;

endmodule