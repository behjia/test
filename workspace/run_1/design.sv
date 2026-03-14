module sync_fifo_16x32 (
    input logic clk,
    input logic rst_n,
    input logic write_en,
    input logic read_en,
    input logic [31:0] data_in,
    output logic [31:0] data_out,
    output logic full,
    output logic empty
);

    logic [31:0] fifo_mem [15:0];
    logic [4:0] count;
    logic read_en_q;

    assign full = (count == 5'd16);
    assign empty = (count == 5'd0);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 5'd0;
            read_en_q <= 1'b0;
            data_out <= 32'd0;
            for (int i = 0; i < 16; i++) begin
                fifo_mem[i] <= 32'd0;
            end
        end else begin
            read_en_q <= read_en;

            if (write_en && !full) begin
                fifo_mem[count] <= data_in;
            end

            if (read_en_q && !empty) begin
                data_out <= fifo_mem[0];
                for (int i = 0; i < 15; i++) begin
                    fifo_mem[i] <= fifo_mem[i+1];
                end
                if (!(write_en && !full)) begin
                    count <= count - 1'b1;
                end
            end else begin
                data_out <= 32'd0;
                if (write_en && !full) begin
                    count <= count + 1'b1;
                end
            end
        end
    end

endmodule