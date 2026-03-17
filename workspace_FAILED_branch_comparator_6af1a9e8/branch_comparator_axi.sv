`default_nettype none

module branch_comparator_axi_wrapper #(
    parameter C_S_AXI_DATA_WIDTH = 32,
    parameter C_S_AXI_ADDR_WIDTH = 4
) (
    // Global Clock and Reset
    input  wire  S_AXI_ACLK,
    input  wire  S_AXI_ARESETN,

    // AXI4-Lite Write Address Channel
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_AWADDR,
    input  wire  S_AXI_AWVALID,
    output wire  S_AXI_AWREADY,

    // AXI4-Lite Write Data Channel
    input  wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_WDATA,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
    input  wire  S_AXI_WVALID,
    output wire  S_AXI_WREADY,

    // AXI4-Lite Write Response Channel
    output wire [1:0] S_AXI_BRESP,
    output wire  S_AXI_BVALID,
    input  wire  S_AXI_BREADY,

    // AXI4-Lite Read Address Channel
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_ARADDR,
    input  wire  S_AXI_ARVALID,
    output wire  S_AXI_ARREADY,

    // AXI4-Lite Read Data Channel
    output wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_RDATA,
    output wire [1:0] S_AXI_RRESP,
    output wire  S_AXI_RVALID,
    input  wire  S_AXI_RREADY
);

    // -------------------------------------------------------------------------
    // AXI4-Lite Handshake Registers
    // -------------------------------------------------------------------------
    reg aw_ready_reg;
    reg w_ready_reg;
    reg b_valid_reg;
    reg ar_ready_reg;
    reg r_valid_reg;
    reg [C_S_AXI_DATA_WIDTH-1:0] r_data_reg;

    assign S_AXI_AWREADY = aw_ready_reg;
    assign S_AXI_WREADY  = w_ready_reg;
    assign S_AXI_BRESP   = 2'b00; // OKAY
    assign S_AXI_BVALID  = b_valid_reg;
    assign S_AXI_ARREADY = ar_ready_reg;
    assign S_AXI_RDATA   = r_data_reg;
    assign S_AXI_RRESP   = 2'b00; // OKAY
    assign S_AXI_RVALID  = r_valid_reg;

    // -------------------------------------------------------------------------
    // Software-Accessible Memory Mapped Registers
    // -------------------------------------------------------------------------
    
    
    reg [31:0] reg_operand_a;
    
    
    
    reg [31:0] reg_operand_b;
    
    
    
    reg [2:0] reg_branch_type;
    
    

    // -------------------------------------------------------------------------
    // Write Logic (CPU to Hardware)
    // -------------------------------------------------------------------------
    always @(posedge S_AXI_ACLK) begin
        if (~S_AXI_ARESETN) begin
            aw_ready_reg <= 1'b0;
            w_ready_reg  <= 1'b0;
            b_valid_reg  <= 1'b0;
            
            
            reg_operand_a <= 0;
            
            
            
            reg_operand_b <= 0;
            
            
            
            reg_branch_type <= 0;
            
            
        end else begin
            // Simple AW and W handshake
            if (S_AXI_AWVALID && ~aw_ready_reg && S_AXI_WVALID && ~w_ready_reg) begin
                aw_ready_reg <= 1'b1;
                w_ready_reg  <= 1'b1;
                b_valid_reg  <= 1'b1;
                
                // Memory Map Decoding (Word Aligned)
                case (S_AXI_AWADDR[3:2])
                    
                    
                    
                    2'd0: reg_operand_a <= S_AXI_WDATA[31:0];
                    
                    
                    
                    
                    2'd0: reg_operand_b <= S_AXI_WDATA[31:0];
                    
                    
                    
                    
                    2'd0: reg_branch_type <= S_AXI_WDATA[2:0];
                    
                    
                    
                    default: ;
                endcase
            end else begin
                aw_ready_reg <= 1'b0;
                w_ready_reg  <= 1'b0;
                if (S_AXI_BREADY && b_valid_reg) b_valid_reg <= 1'b0;
            end
        end
    end

    // -------------------------------------------------------------------------
    // Core AI Logic Instantiation (The LLM's Output)
    // -------------------------------------------------------------------------
    
    wire [0:0] core_out_branch_taken;
    
    wire [0:0] core_out_eq_flag;
    
    wire [0:0] core_out_lt_signed;
    
    wire [0:0] core_out_lt_unsigned;
    

    branch_comparator core_inst (
        
        
        
        .operand_a(reg_operand_a),
        
        
        
        .operand_b(reg_operand_b),
        
        
        
        .branch_type(reg_branch_type),
        
        
        
        .branch_taken(core_out_branch_taken),
        
        .eq_flag(core_out_eq_flag),
        
        .lt_signed(core_out_lt_signed),
        
        .lt_unsigned(core_out_lt_unsigned)
        
    );

    // -------------------------------------------------------------------------
    // Read Logic (Hardware to CPU)
    // -------------------------------------------------------------------------
    always @(posedge S_AXI_ACLK) begin
        if (~S_AXI_ARESETN) begin
            ar_ready_reg <= 1'b0;
            r_valid_reg  <= 1'b0;
            r_data_reg   <= 0;
        end else begin
            if (S_AXI_ARVALID && ~ar_ready_reg) begin
                ar_ready_reg <= 1'b1;
                r_valid_reg  <= 1'b1;
                // Read from Output Port 0 (assuming single primary output for now)
                r_data_reg <= { {(C_S_AXI_DATA_WIDTH - 1){1'b0}}, core_out_branch_taken };
            end else begin
                ar_ready_reg <= 1'b0;
                if (S_AXI_RREADY && r_valid_reg) r_valid_reg <= 1'b0;
            end
        end
    end

endmodule