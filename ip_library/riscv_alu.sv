module riscv_alu_32bit (
    input  logic [31:0] alu_in1,
    input  logic [31:0] alu_in2,
    input  logic [3:0]  alu_control,
    output logic [31:0] alu_result,
    output logic        zero_flag
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    logic [31:0] add_result;
    logic [31:0] sub_result;
    logic [31:0] and_result;
    logic [31:0] or_result;
    logic [31:0] xor_result;
    logic [31:0] slt_result;
    logic [31:0] sltu_result;
    logic [31:0] sll_result;
    logic [31:0] srl_result;
    logic [31:0] sra_result;

    always_comb begin
        add_result  = alu_in1 + alu_in2;
        sub_result  = alu_in1 - alu_in2;
        and_result  = alu_in1 & alu_in2;
        or_result   = alu_in1 | alu_in2;
        xor_result  = alu_in1 ^ alu_in2;
        slt_result  = ($signed(alu_in1) < $signed(alu_in2)) ? 32'd1 : 32'd0;
        sltu_result = (alu_in1 < alu_in2) ? 32'd1 : 32'd0;
        sll_result  = alu_in1 << alu_in2[4:0];
        srl_result  = alu_in1 >> alu_in2[4:0];
        sra_result  = $signed(alu_in1) >>> alu_in2[4:0];

        case (alu_control)
            4'b0000: alu_result = add_result;
            4'b0001: alu_result = sub_result;
            4'b0010: alu_result = and_result;
            4'b0011: alu_result = or_result;
            4'b0100: alu_result = xor_result;
            4'b0101: alu_result = slt_result;
            4'b0110: alu_result = sltu_result;
            4'b0111: alu_result = sll_result;
            4'b1000: alu_result = srl_result;
            4'b1001: alu_result = sra_result;
            default: alu_result = 32'd0;
        endcase

        zero_flag = (alu_result == 32'd0);
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_alu_32bit);
    end
    `endif
endmodule