module adder_4bit (
  input logic [3:0] a,
  input logic [3:0] b,
  output logic [4:0] sum
);

  logic [4:0] carry;
  logic [3:0] p;
  logic [3:0] g;

  // Generate propagate and generate signals
  always_comb begin
    p = a ^ b;
    g = a & b;
  end

  // Carry lookahead logic
  always_comb begin
    carry[0] = 1'b0;
    carry[1] = g[0] | (p[0] & carry[0]);
    carry[2] = g[1] | (p[1] & g[0]) | (p[1] & p[0] & carry[0]);
    carry[3] = g[2] | (p[2] & g[1]) | (p[2] & p[1] & g[0]) | (p[2] & p[1] & p[0] & carry[0]);
    carry[4] = g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) | (p[3] & p[2] & p[1] & g[0]) | (p[3] & p[2] & p[1] & p[0] & carry[0]);
  end

  // Sum calculation
  always_comb begin
    sum[0] = p[0] ^ carry[0];
    sum[1] = p[1] ^ carry[1];
    sum[2] = p[2] ^ carry[2];
    sum[3] = p[3] ^ carry[3];
    sum[4] = carry[4];
  end

  `ifndef SYNTHESIS
  initial begin
    #1;
  end
  `endif

endmodule