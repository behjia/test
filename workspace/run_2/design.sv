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
    logic [4:0] sub_result;

    // Parallel computation for maximum performance
    assign add_result = {1'b0, a} + {1'b0, b};
    assign sub_result = {1'b0, a} - {1'b0, b};
    
    // AND and OR operations
    assign logic_result = (opcode[1:0] == 2'b10) ? (a & b) : (a | b);

    // Opcode mapping:
    // 2'b00: ADD
    // 2'b01: SUB
    // 2'b10: AND
    // 2'b11: OR
    
    always_comb begin
        case (opcode)
            2'b00: begin
                result = add_result[3:0];
                carry_out = add_result[4];
            end
            2'b01: begin
                result = sub_result[3:0];
                carry_out = sub_result[4];
            end
            2'b10: begin
                result = a & b;
                carry_out = 1'b0;
            end
            2'b11: begin
                result = a | b;
                carry_out = 1'b0;
            end
            default: begin
                result = 4'b0000;
                carry_out = 1'b0;
            end
        endcase
    end

    // Zero flag generation
    assign zero_flag = (result == 4'b0000) ? 1'b1 : 1'b0;

endmodule