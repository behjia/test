module sync_fifo_16x32 #(
    parameter integer DEPTH = 16,
    parameter integer WIDTH = 32
)(
    input  logic        clk,
    input  logic        rst_n,
    input  logic        write_en,
    input  logic        read_en,
    input  logic [31:0] data_in,
    output logic [31:0] data_out,
    output logic        full,
    output logic        empty
);

    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [$clog2(DEPTH):0] count;
    logic [$clog2(DEPTH)-1:0] wr_ptr;
    logic [$clog2(DEPTH)-1:0] rd_ptr;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count    <= '0;
            wr_ptr   <= '0;
            rd_ptr   <= '0;
            data_out <= '0;
        end else begin
            if (write_en && !full) begin
                mem[wr_ptr] <= data_in;
                wr_ptr      <= wr_ptr + 1'b1;
            end
            
            if (read_en && !empty) begin
                data_out <= mem[rd_ptr];
                rd_ptr   <= rd_ptr + 1'b1;
            end else if (!empty) begin
                data_out <= mem[rd_ptr];
            end else begin
                data_out <= '0;
            end

            if (write_en && !full && !(read_en && !empty)) begin
                count <= count + 1'b1;
            end else if (!(write_en && !full) && read_en && !empty) begin
                count <= count - 1'b1;
            end
        end
    end

endmodule