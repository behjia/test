module riscv_alu #(
    parameter DATA_WIDTH = 32
)(
    input  logic [DATA_WIDTH-1:0] a,
    input  logic [DATA_WIDTH-1:0] b,
    input  logic [3:0]            alu_ctrl,
    output logic [DATA_WIDTH-1:0] result,
    output logic                  zero
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    // ALU Control Codes (localparam for clarity)
    localparam [3:0] ALU_ADD  = 4'b0000;
    localparam [3:0] ALU_SUB  = 4'b0001;
    localparam [3:0] ALU_AND  = 4'b0010;
    localparam [3:0] ALU_OR   = 4'b0011;
    localparam [3:0] ALU_XOR  = 4'b0100;
    localparam [3:0] ALU_SLL  = 4'b0101;
    localparam [3:0] ALU_SRL  = 4'b0110;
    localparam [3:0] ALU_SRA  = 4'b0111;
    localparam [3:0] ALU_SLT  = 4'b1000;
    localparam [3:0] ALU_SLTU = 4'b1001;

    // Parallel computation of all operations (speed-optimized)
    logic [DATA_WIDTH-1:0] add_result;
    logic [DATA_WIDTH-1:0] sub_result;
    logic [DATA_WIDTH-1:0] and_result;
    logic [DATA_WIDTH-1:0] or_result;
    logic [DATA_WIDTH-1:0] xor_result;
    logic [DATA_WIDTH-1:0] sll_result;
    logic [DATA_WIDTH-1:0] srl_result;
    logic [DATA_WIDTH-1:0] sra_result;
    logic [DATA_WIDTH-1:0] slt_result;
    logic [DATA_WIDTH-1:0] sltu_result;

    // Parallel computation
    assign add_result  = a + b;
    assign sub_result  = a - b;
    assign and_result  = a & b;
    assign or_result   = a | b;
    assign xor_result  = a ^ b;
    assign sll_result  = a << b[4:0];
    assign srl_result  = a >> b[4:0];
    assign sra_result  = $signed(a) >>> b[4:0];
    assign slt_result  = {{(DATA_WIDTH-1){1'b0}}, ($signed(a) < $signed(b))};
    assign sltu_result = {{(DATA_WIDTH-1){1'b0}}, (a < b)};

    // Truth Table for ALU Control:
    // alu_ctrl | Operation | result
    // ---------+-----------+------------------
    //   0000   |    ADD    | a + b
    //   0001   |    SUB    | a - b
    //   0010   |    AND    | a & b
    //   0011   |    OR     | a | b
    //   0100   |    XOR    | a ^ b
    //   0101   |    SLL    | a << b[4:0]
    //   0110   |    SRL    | a >> b[4:0]
    //   0111   |    SRA    | a >>> b[4:0]
    //   1000   |    SLT    | signed(a) < signed(b)
    //   1001   |   SLTU    | a < b
    //  others  |  default  | 0

    // Wide multiplexer for final result selection
    always_comb begin
        case (alu_ctrl)
            ALU_ADD:  result = add_result;
            ALU_SUB:  result = sub_result;
            ALU_AND:  result = and_result;
            ALU_OR:   result = or_result;
            ALU_XOR:  result = xor_result;
            ALU_SLL:  result = sll_result;
            ALU_SRL:  result = srl_result;
            ALU_SRA:  result = sra_result;
            ALU_SLT:  result = slt_result;
            ALU_SLTU: result = sltu_result;
            default:  result = {DATA_WIDTH{1'b0}};
        endcase
    end

    // Zero flag generation
    assign zero = (result == {DATA_WIDTH{1'b0}});


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_alu);
    end
    `endif
endmodule