module multiplier_8bit (
  input logic [7:0] a,
  input logic [7:0] b,
  output logic [15:0] p
);

  logic [15:0] result;
  
  always_comb begin
    result = a * b;
  end
  
  assign p = result;

endmodule