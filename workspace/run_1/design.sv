```systemverilog
module sync_up_counter_8bit (
  input wire clk,
  input wire rst_n,
  input wire enable,
  output reg [7:0] count
);

  reg [7:0] count_next;
  wire [7:0] sum;

  // Kogge-Stone Parallel Prefix Adder for 8-bit increment
  // Stage 0: Initial sum and carry computation
  wire [7:0] g0, p0;
  
  assign p0[0] = 1'b1;  // propagate for bit 0 (always adding 1)
  assign g0[0] = 1'b0;  // generate for bit 0
  
  assign p0[1] = count[1];
  assign g0[1] = count[0];
  
  assign p0[2] = count[2];
  assign g0[2] = count[1] & count[0];
  
  assign p0[3] = count[3];
  assign g0[3] = count[2] & count[1] & count[0];
  
  assign p0[4] = count[4];
  assign g0[4] = count[3] & count[2] & count[1] & count[0];
  
  assign p0[5] = count[5];
  assign g0[5] = count[4] & count[3] & count[2] & count[1] & count[0];
  
  assign p0[6] = count[6];
  assign g0[6] = count[5] & count[4] & count[3] & count[2] & count[1] & count[0];
  
  assign p0[7] = count[7];
  assign g0[7] = count[6] & count[5] & count[4] & count[3] & count[2] & count[1] & count[0];
  
  // Stage 1: First level of parallel prefix computation
  wire [7:0] g1, p1;
  
  assign p1[0] = p0[0];
  assign g1[0] = g0[0];
  
  assign p1[1] = p0[1] & p0[0];
  assign g1[1] = g0[1] | (p0[1] & g0[0]);
  
  assign p1[2] = p0[2] & p0[1];
  assign g1[2] = g0[2] | (p0[2] & g0[1]);
  
  assign p1[3] = p0[3] & p0[2] & p0[1] & p0[0];
  assign g1[3] = g0[3] | (p0[3] & g0[2]) | (p0[3] & p0[2] & g0[1]) | (p0[3] & p0[2] & p0[1] & g0[0]);
  
  assign p1[4] = p0[4] & p0[3];
  assign g1[4] = g0[4] | (p0[4] & g0[3]);
  
  assign p1[5] = p0[5] & p0[4] & p0[3];
  assign g1[5] = g0[5] | (p0[5] & g0[4]) | (p0[5] & p0[4] & g0[3]);
  
  assign p1[6] = p0[6] & p0[5] & p0[4];
  assign g1[6] = g0[6] | (p0[6] & g0[5]) | (p0[6] & p0[5] & g0[4]);
  
  assign p1[7] = p0[7] & p0[6] & p0[5] & p0[4];
  assign g1[7] = g0[7] | (p0[7] & g0[6]) | (p0[7] & p0[6] & g0[5]) | (p0[7] & p0