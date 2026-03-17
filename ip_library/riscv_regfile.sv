module riscv_register_file #(
    parameter DATA_WIDTH = 32,
    parameter NUM_REGS = 32,
    parameter ADDR_WIDTH = 5
)(
    input  logic                     clk,
    input  logic                     rst_n,
    input  logic [4:0]               rs1_addr,
    input  logic [4:0]               rs2_addr,
    input  logic [4:0]               rd_addr,
    input  logic [DATA_WIDTH-1:0]    rd_data,
    input  logic                     reg_write_enable,
    output logic [DATA_WIDTH-1:0]    rs1_data,
    output logic [DATA_WIDTH-1:0]    rs2_data
);

    logic [DATA_WIDTH-1:0] registers [NUM_REGS-1:0];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < NUM_REGS; i++) begin
                registers[i] <= '0;
            end
        end else begin
            if (reg_write_enable && (rd_addr != 5'b00000)) begin
                registers[rd_addr] <= rd_data;
            end
        end
    end

    always_comb begin
        if (rs1_addr == 5'b00000) begin
            rs1_data = '0;
        end else if (reg_write_enable && (rs1_addr == rd_addr)) begin
            rs1_data = rd_data;
        end else begin
            rs1_data = registers[rs1_addr];
        end
    end

    always_comb begin
        if (rs2_addr == 5'b00000) begin
            rs2_data = '0;
        end else if (reg_write_enable && (rs2_addr == rd_addr)) begin
            rs2_data = rd_data;
        end else begin
            rs2_data = registers[rs2_addr];
        end
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_register_file);
    end
    `endif
endmodule