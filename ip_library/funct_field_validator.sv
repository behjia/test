module rtype_validator (
    input  logic [2:0] funct3,
    input  logic [6:0] funct7,
    output logic       is_valid
);

    `ifndef SYNTHESIS
    initial begin #1; end
    `endif

    // Internal probes for visibility
    logic probe_funct3_match;
    logic probe_funct7_match;
    logic [9:0] probe_combined_fields;

    // Valid instruction encoding lookup table
    // Each entry represents a valid {funct7, funct3} combination
    // For this design, only ADD instruction is valid:
    // ADD: funct7=7'b0000000, funct3=3'b000
    localparam int NUM_VALID_ENCODINGS = 1;
    localparam logic [9:0] VALID_ENCODINGS [NUM_VALID_ENCODINGS] = '{
        10'b0000000_000  // ADD instruction
    };

    // Combine funct7 and funct3 for lookup
    assign probe_combined_fields = {funct7, funct3};

    // Probe individual field matches for the ADD instruction
    assign probe_funct3_match = (funct3 == 3'b000);
    assign probe_funct7_match = (funct7 == 7'b0000000);

    // Lookup table validation logic
    always_comb begin
        is_valid = 1'b0;  // Default to invalid
        
        // Search through valid encodings
        for (int i = 0; i < NUM_VALID_ENCODINGS; i++) begin
            if (probe_combined_fields == VALID_ENCODINGS[i]) begin
                is_valid = 1'b1;
            end
        end
    end


    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, rtype_validator);
    end
    `endif
endmodule