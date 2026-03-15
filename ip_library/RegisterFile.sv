module riscv_register_file #(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 5
)(
    input  logic                    clk,
    input  logic                    reset,
    input  logic [ADDR_WIDTH-1:0]   rs1,
    input  logic [ADDR_WIDTH-1:0]   rs2,
    input  logic [ADDR_WIDTH-1:0]   rd,
    input  logic [DATA_WIDTH-1:0]   write_data,
    input  logic                    reg_write,
    output logic [DATA_WIDTH-1:0]   read_data1,
    output logic [DATA_WIDTH-1:0]   read_data2
);

    // Register file storage: 32 registers of DATA_WIDTH bits each
    logic [DATA_WIDTH-1:0] registers [0:2**ADDR_WIDTH-1];

    // Synchronous write with x0 hardwired to zero
    always_ff @(posedge clk) begin
        if (reset) begin
            // Initialize all registers to zero on reset
            for (int i = 0; i < 2**ADDR_WIDTH; i++) begin
                registers[i] <= {DATA_WIDTH{1'b0}};
            end
        end else begin
            // Write to register file
            // HARDWARE RULE: Register x0 (rd == 0) is hardwired to 0, writes are ignored
            if (reg_write && (rd != {ADDR_WIDTH{1'b0}})) begin
                registers[rd] <= write_data;
            end
        end
    end

    // Synchronous read port 1 (registered output)
    // HARDWARE RULE: Reading x0 always returns 32'b0
    always_ff @(posedge clk) begin
        if (reset) begin
            read_data1 <= {DATA_WIDTH{1'b0}};
        end else begin
            if (rs1 == {ADDR_WIDTH{1'b0}}) begin
                read_data1 <= {DATA_WIDTH{1'b0}};
            end else begin
                read_data1 <= registers[rs1];
            end
        end
    end

    // Synchronous read port 2 (registered output)
    // HARDWARE RULE: Reading x0 always returns 32'b0
    always_ff @(posedge clk) begin
        if (reset) begin
            read_data2 <= {DATA_WIDTH{1'b0}};
        end else begin
            if (rs2 == {ADDR_WIDTH{1'b0}}) begin
                read_data2 <= {DATA_WIDTH{1'b0}};
            end else begin
                read_data2 <= registers[rs2];
            end
        end
    end

    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_register_file);
    end
    `endif
endmodule