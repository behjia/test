module adder_4bit (
  input  logic [3:0] a,
  input  logic [3:0] b,
  output logic [4:0] sum
);

  logic [4:0] carry;
  
  assign carry[0] = 1'b0;
  
  genvar i;
  generate
    for (i = 0; i < 4; i = i + 1) begin : full_adder_chain
      assign sum[i] = a[i] ^ b[i] ^ carry[i];
      assign carry[i+1] = (a[i] & b[i]) | ((a[i] ^ b[i]) & carry[i]);
    end
  endgenerate
  
  assign sum[4] = carry[4];

  `ifndef SYNTHESIS
  
  `endif

endmodule