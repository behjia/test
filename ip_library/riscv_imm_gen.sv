module riscv_imm_gen (
    input  logic [31:0] instruction,
    input  logic  [2:0] imm_format,
    output logic [31:0] immediate
);

  `ifndef SYNTHESIS
  initial begin #1; end
  `endif

  // Format encoding truth table:
  // imm_format | Format | Immediate Bits
  // -----------|--------|-------------------------------------------
  //    3'b000  | I-type | sign_extend(inst[31:20])
  //    3'b001  | S-type | sign_extend({inst[31:25], inst[11:7]})
  //    3'b010  | B-type | sign_extend({inst[31], inst[7], inst[30:25], inst[11:8], 1'b0})
  //    3'b011  | U-type | {inst[31:12], 12'b0}
  //    3'b100  | J-type | sign_extend({inst[31], inst[19:12], inst[20], inst[30:21], 1'b0})
  //    default | zero   | 32'b0

  always_comb begin
    case (imm_format)
      // I-type: 12-bit immediate [31:20]
      3'b000: begin
        immediate = {{20{instruction[31]}}, instruction[31:20]};
      end

      // S-type: 12-bit immediate [31:25][11:7]
      3'b001: begin
        immediate = {{20{instruction[31]}}, instruction[31:25], instruction[11:7]};
      end

      // B-type: 13-bit immediate [31][7][30:25][11:8][0]
      3'b010: begin
        immediate = {{19{instruction[31]}}, instruction[31], instruction[7], 
                     instruction[30:25], instruction[11:8], 1'b0};
      end

      // U-type: 20-bit immediate [31:12] in upper bits
      3'b011: begin
        immediate = {instruction[31:12], 12'b0};
      end

      // J-type: 21-bit immediate [31][19:12][20][30:21][0]
      3'b100: begin
        immediate = {{11{instruction[31]}}, instruction[31], instruction[19:12], 
                     instruction[20], instruction[30:21], 1'b0};
      end

      // Default: zero output
      default: begin
        immediate = 32'b0;
      end
    endcase
  end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, riscv_imm_gen);
    end
    `endif
endmodule