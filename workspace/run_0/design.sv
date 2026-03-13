module sync_up_counter_8bit (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       enable,
  output logic [7:0] count
);

  logic [7:0] count_next;

  // Ripple-carry adder logic
  always_comb begin
    if (enable) begin
      count_next = count + 8'd1;
    end else begin
      count_next = count;
    end
  end

  // Sequential logic with active-low reset
  always_ff @(posedge clk) begin
    if (~rst_n) begin
      count <= 8'd0;
    end else begin
      count <= count_next;
    end
  end

endmodule