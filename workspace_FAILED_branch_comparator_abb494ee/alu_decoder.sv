module alu_decoder (

    input logic [1:0] alu_op,

    input logic [2:0] funct3,

    input logic [6:0] funct7,


    output logic [2:0] alu_control

);

// --- AI GENERATED INTERNAL LOGIC ---
// ALU Control Encoding (based on RISC-V standard):
// 3'b000: ADD
// 3'b001: SUB
// 3'b010: AND
// 3'b011: OR
// (Other encodings reserved for future operations)

// Internal probes for debugging
logic probe_alu_op_00;
logic probe_alu_op_01;
logic probe_alu_op_10;
logic probe_funct3_match;
logic probe_funct7_match;

assign probe_alu_op_00 = (alu_op == 2'b00);
assign probe_alu_op_01 = (alu_op == 2'b01);
assign probe_alu_op_10 = (alu_op == 2'b10);
assign probe_funct3_match = (funct3 == 3'b000);
assign probe_funct7_match = (funct7 == 7'b0100000);

// Truth Table:
// alu_op | funct3 | funct7[5] | Operation | alu_control
// ---------|--------|-----------|-----------|-------------
//   00     |   X    |     X     |    ADD    |    000
//   01     |   X    |     X     |    SUB    |    001
//   10     |  000   |     0     |    ADD    |    000
//   10     |  000   |     1     |    SUB    |    001
//   10     |  111   |     X     |    AND    |    010
//   10     |  110   |     X     |    OR     |    011
//   others |   X    |     X     |    ADD    |    000 (default)

always_comb begin
    alu_control = 3'b000; // Default: ADD
    
    case (alu_op)
        2'b00: begin
            // Load/Store operations - always ADD for address calculation
            alu_control = 3'b000;
        end
        
        2'b01: begin
            // Branch operations - always SUB for comparison
            alu_control = 3'b001;
        end
        
        2'b10: begin
            // R-type and I-type ALU operations
            case (funct3)
                3'b000: begin
                    // ADD or SUB based on funct7[5]
                    if (funct7[5])
                        alu_control = 3'b001; // SUB
                    else
                        alu_control = 3'b000; // ADD
                end
                
                3'b111: begin
                    // AND operation
                    alu_control = 3'b010;
                end
                
                3'b110: begin
                    // OR operation
                    alu_control = 3'b011;
                end
                
                default: begin
                    // Unsupported funct3 - default to ADD
                    alu_control = 3'b000;
                end
            endcase
        end
        
        default: begin
            // Unsupported alu_op - default to ADD
            alu_control = 3'b000;
        end
    endcase
end
// -----------------------------------


`ifndef SYNTHESIS
initial begin
    $dumpfile("sim_build/dump.vcd");
    $dumpvars(0, alu_decoder);
end
`endif

endmodule

