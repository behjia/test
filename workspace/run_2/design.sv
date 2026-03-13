module sync_up_counter_8bit (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    output logic [7:0] count
);

    logic [7:0] count_next;
    logic [3:0] lower_sum;
    logic       lower_carry;
    logic [3:0] upper_sum;

    // Carry-lookahead adder for lower 4 bits
    logic [3:0] lower_p;
    logic [3:0] lower_g;
    logic       c1, c2, c3, c4;

    // Generate propagate and generate signals for lower 4 bits
    assign lower_p[0] = count[0];
    assign lower_g[0] = count[0];
    assign lower_p[1] = count[1] ^ count[0];
    assign lower_g[1] = count[1] & count[0];
    assign lower_p[2] = count[2] ^ (count[1] & count[0]);
    assign lower_g[2] = count[2] & (count[1] & count[0]);
    assign lower_p[3] = count[3] ^ (count[2] & count[1] & count[0]);
    assign lower_g[3] = count[3] & (count[2] & count[1] & count[0]);

    // Carry computation for CLA (lower 4 bits)
    assign c1 = lower_g[0];
    assign c2 = lower_g[1] | (lower_p[1] & lower_g[0]);
    assign c3 = lower_g[2] | (lower_p[2] & lower_g[1]) | (lower_p[2] & lower_p[1] & lower_g[0]);
    assign c4 = lower_g[3] | (lower_p[3] & lower_g[2]) | (lower_p[3] & lower_p[2] & lower_g[1]) | (lower_p[3] & lower_p[2] & lower_p[1] & lower_g[0]);

    // Sum computation for lower 4 bits
    assign lower_sum[0] = count[0] ^ 1'b1;
    assign lower_sum[1] = count[1] ^ c1;
    assign lower_sum[2] = count[2] ^ c2;
    assign lower_sum[3] = count[3] ^ c3;
    assign lower_carry = c4;

    // Ripple-carry adder for upper 4 bits
    assign upper_sum[0] = count[4] ^ lower_carry;
    assign upper_sum[1] = count[5] ^ (count[4] & lower_carry);
    assign upper_sum[2] = count[6] ^ (count[5] & count[4] & lower_carry);
    assign upper_sum[3] = count[7] ^ (count[6] & count[5] & count[4] & lower_carry);

    // Mux for enable
    assign count_next = enable ? {upper_sum, lower_sum} : count;

    // Sequential logic with active-low reset
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 8'b0;
        end else begin
            count <= count_next;
        end
    end

endmodule