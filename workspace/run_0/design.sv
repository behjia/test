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

    logic [3:0] wr_ptr;
    logic [3:0] rd_ptr;
    logic [4:0] count;
    logic [31:0] mem [15:0];
    logic read_en_q;

    assign full = (count == 5'd16);
    assign empty = (count == 5'd0);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 4'd0;
            rd_ptr <= 4'd0;
            count <= 5'd0;
            read_en_q <= 1'b0;
            data_out <= 32'd0;
        end else begin
            read_en_q <= read_en;

            if (write_en && !full) begin
                mem[wr_ptr] <= data_in;
                wr_ptr <= wr_ptr + 4'd1;
            end

            if (read_en_q && !empty) begin
                data_out <= mem[rd_ptr];
                rd_ptr <= rd_ptr + 4'd1;
            end else begin
                data_out <= 32'd0;
            end

            if ((write_en && !full) && !(read_en_q && !empty)) begin
                count <= count + 5'd1;
            end else if (!(write_en && !full) && (read_en_q && !empty)) begin
                count <= count - 5'd1;
            end
        end
    end

endmodule