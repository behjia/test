module adder_4bit (
  input  logic [3:0] a,
  input  logic [3:0] b,
  output logic [4:0] sum
);

  // Kogge-Stone parallel prefix adder for 4-bit addition
  // This implementation uses parallel prefix computation for minimal latency
  
  logic [3:0] p_initial;  // Initial propagate
  logic [3:0] g_initial;  // Initial generate
  
  // Stage 0: Compute initial propagate and generate
  assign p_initial = a ^ b;
  assign g_initial = a & b;
  
  // Kogge-Stone parallel prefix computation
  // Level 1: distance 1
  logic [3:0] p_l1, g_l1;
  
  assign p_l1[0] = p_initial[0];
  assign g_l1[0] = g_initial[0];
  
  assign p_l1[1] = p_initial[1] & p_initial[0];
  assign g_l1[1] = g_initial[1] | (p_initial[1] & g_initial[0]);
  
  assign p_l1[2] = p_initial[2] & p_initial[1];
  assign g_l1[2] = g_initial[2] | (p_initial[2] & g_initial[1]);
  
  assign p_l1[3] = p_initial[3] & p_initial[2];
  assign g_l1[3] = g_initial[3] | (p_initial[3] & g_initial[2]);
  
  // Level 2: distance 2
  logic [3:0] p_l2, g_l2;
  
  assign p_l2[0] = p_l1[0];
  assign g_l2[0] = g_l1[0];
  
  assign p_l2[1] = p_l1[1];
  assign g_l2[1] = g_l1[1];
  
  assign p_l2[2] = p_l1[2] & p_l1[0];
  assign g_l2[2] = g_l1[2] | (p_l1[2] & g_l1[0]);
  
  assign p_l2[3] = p_l1[3] & p_l1[1];
  assign g_l2[3] = g_l1[3] | (p_l1[3] & g_l1[1]);
  
  // Final carry computation
  logic [4:0] carries;
  assign carries[0] = 1'b0;  // Initial carry in is 0
  assign carries[1] = g_l2[0];
  assign carries[2] = g_l2[1] | (p_l2[1] & g_l2[0]);
  assign carries[3] = g_l2[2] | (p_l2[2] & g_l2[1]) | (p_l2[2] & p_l2[1] & g_l2[0]);
  assign carries[4] = g_l2[3] | (p_l2[3] & g_l2[2]) | (p_l2[3] & p_l2[2] & g_l2[1]) | (p_l2[3] & p_l2[2] & p_l2[1] & g_l2[0]);
  
  // Final sum computation
  assign sum[0] = p_initial[0] ^ carries[0];
  assign sum[1] = p_initial[1] ^ carries[1];
  assign sum[2] = p_initial[2] ^ carries[2];
  assign sum[3] = p_initial[3] ^ carries[3];
  assign sum[4] = carries[4];
  
  `ifndef SYNTHESIS
  
  `endif

endmodule