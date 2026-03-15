module program_counter #(
  parameter WIDTH = 32,
  parameter RESET_VECTOR = 0
)(
  input  logic clk,
  input  logic rst,
  input  logic [31:0] next_pc,
  output logic [31:0] pc
);

  // Area-optimized implementation using explicit flip-flop instantiation
  // This approach allows synthesis tools to map directly to specific
  // standard cell flip-flops for optimal area
  
  genvar i;
  generate
    for (i = 0; i < WIDTH; i++) begin : pc_reg_gen
      // Explicit D flip-flop with synchronous reset
      always_ff @(posedge clk) begin
        if (rst)
          pc[i] <= RESET_VECTOR[i];
        else
          pc[i] <= next_pc[i];
      end
    end
  endgenerate


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, program_counter);
    end
    `endif
endmodule