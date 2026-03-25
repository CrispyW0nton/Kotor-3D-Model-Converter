%using Kotor.NET.Compiler.Compilation;

%namespace Kotor.NET.Compiler.Calculator
%partial
%parsertype CalculatorParser
%visibility internal
%tokentype Token

%union { 
       public object node;
       public string text;
       public float numberf;
       public int numberi;
       public DataType datatype;
       }
%start compilation_unit


%token EOL, NOP, COMMENT_INLINE, COMMENT_MULTILINE, INCLUDE, VALUE_OBJECT_SELF,
       VALUE_OBJECT_INVALID, VALUE_TRUE, VALUE_FALSE, FLOW_BREAK, FLOW_CONTINUE,
       FLOW_CASE, FLOW_DEFAULT, FLOW_DO, FLOW_ELSE, FLOW_SWITCH, FLOW_FOR,
       FLOW_IF, FLOW_RETURN, TYPE_STRUCT, TYPE_INT, TYPE_FLOAT, TYPE_OBJECT,
       TYPE_VOID, TYPE_EVENT, TYPE_EFFECT, TYPE_ITEM_PROPERTY, TYPE_LOCATION,
       TYPE_STRING, TYPE_TALENT, TYPE_ACTION, TYPE_VECTOR, IDENTIFIER,
       LITERAL_STRING, LITERAL_FLOAT, LITERAL_INT_HEX, LITERAL_INT,
       OP_INCREMENT, OP_DECREMENT, ASSIGNMENT_ADD, ASSIGNMENT_SUBTRACT,
       ASSIGNMENT_DIVISION, OP_BITWISE_LEFT, OP_BITWISE_RIGHT, OP_ADD, OP_SUBTRACT,
       OP_MULTIPLY, OP_DIVIDE, OP_EQUALITY, OP_INEQUALITY, OP_GREATER_THAN_OR_EQUAL,
       OP_GREATER_THAN, OP_LESS_THAN_OR_EQUAL, OP_LESS_THAN, OP_LOGICAL_AND,
       OP_LOGICAL_OR, OP_NOT, OP_BITWISE_AND, OP_BITWISE_OR, OP_BITWISE_XOR,
       OP_BITWISE_NOT, OP_MODULUS, ASSIGNMENT_MULTIPLY, FLOW_WHILE

%%

compilation_unit     : declarations                                         { $$.node = new CompilationUnit((List<ASTNode>)$1.node); }
                     |                                                      { $$.node = new CompilationUnit(); }
                     ;

declarations         : declarations declaration                             { $$.node = $1.node; var node = (ASTNode)$1.node; ((List<ASTNode>)$$.node).Add(node); }
                     | declaration                                          { $$.node = new List<ASTNode>() { (ASTNode)$1.node }; }
                     ;

declaration          : global_variable_declaration                          { $$.node = $1.node; }
                     | script_inclusion                                     { $$.node = $1.node; }
                     | global_variable_initialization                       { $$.node = $1.node; }
                     | function_definition                                  { $$.node = $1.node; }
                     | function_forward_declaration                         { $$.node = $1.node; }
                     | struct_definition                                    { $$.node = $1.node; }
                     ;

                     
global_variable_declaration        : data_type IDENTIFIER ';'                   { $$.node = new GlobalVariableDeclaration($1.datatype, $2.text); }
                                   ;

global_variable_initialization     : data_type IDENTIFIER '=' expression ';'    { ; }
                                   ;

              

script_inclusion     : INCLUDE LITERAL_STRING                                { ; }
                     ;

function_definition         : data_type IDENTIFIER '(' function_definition_params ')' '{' code_block '}'
                            ;


function_forward_declaration : data_type IDENTIFIER '(' function_definition_params ')' ';'      { ; }
                             ;

function_definition_params  : function_definition_params ',' function_definition_param          { ; }
                            | function_definition_param                                         { ; }
                            |                                                                   { ; }
                            ;

function_definition_param   : data_type IDENTIFIER                                              { ; }
                            | data_type IDENTIFIER '=' expression                               { ; }
                            ;


code_block                  : code_block statement
                            |
                            ;

scoped_block                : '{' code_block '}'
                            ;


struct_definition    : TYPE_STRUCT IDENTIFIER struct_member    { ; }
                     ;

struct_members       : struct_members struct_member                          { ; }
                     |                                                       { ; }
                     ;

struct_member        : data_type IDENTIFIER ';'                              { ; }
                     ;


statement            : ';'
                     | declaration_statement
                     | condition_statement
                     | return_statement
                     | while_statement
                     | do_statement
                     | for_statement
                     | switch_statement
                     | break_statement
                     | continue_statement
                     | scoped_block
                     | expression ';'
                     ;

declaration_statement : data_type variable_declarators ';'
                      ;

condition_statement  : if_statement else_if_statements else_statement
                     ;

if_statement         : FLOW_IF '(' expression ')' '{' code_block '}'
                     | FLOW_IF '(' expression ')' statement
                     ;

else_if_statements   : FLOW_ELSE FLOW_IF '(' expression ')' '{' code_block '}'
                     | FLOW_ELSE FLOW_IF '(' expression ')' statement
                     ;

else_statement       : FLOW_ELSE '{' code_block '}'
                     | FLOW_ELSE statement
                     ;

return_statement     : FLOW_RETURN ';'
                     | FLOW_RETURN expression ';'
                     ;

switch_statement     : FLOW_SWITCH '(' expression ')' '{' switch_blocks '}'
                     ;

break_statement      : FLOW_BREAK ';'
                     ;

continue_statement   : FLOW_CONTINUE ';'
                     ;

while_statement      : FLOW_WHILE '(' expression ')'
                     ;

do_statement         : FLOW_DO '{' code_block '}' FLOW_WHILE '(' expression ')' ';'
                     ;

for_statement             : FLOW_FOR '(' expression ';' expression ';' expression ')' '{' code_block '}'
                     ;


variable_declarators : variable_declarators ',' variable_declarator
                     | variable_declarator
                     ;

variable_declarator  : IDENTIFIER
                     | IDENTIFIER '=' expression
                     ;


switch_blocks        : switch_blocks switch_block
                     |
                     ;

switch_block         : switch_labels block_statements
                     |
                     ;

switch_labels        : switch_blocks switch_label
                     |
                     ;

switch_label         : FLOW_CASE expression ':'
                     | FLOW_DEFAULT ':'
                     ;

block_statements     : block_statements statement
                     |
                     ;


function_call        : IDENTIFIER '(' argument_list ')'
                     ;

argument_list        : argument_list ',' expression
                     | expression
                     ;


assignment           : field_access ASSIGNMENT_ADD expression
                     | field_access ASSIGNMENT_SUBTRACT expression
                     | field_access ASSIGNMENT_MULTIPLY expression
                     | field_access ASSIGNMENT_DIVISION expression
                     | field_access '=' expression
                     ;


expression           : '(' expression ')'                               { ; }
                     | assignment                                       { ; }
                     | IDENTIFIER                                       { ; }
                     | function_call                                    { ; }
                     | constant_expression                              { ; }
                     | expression OP_GREATER_THAN expression
                     | expression OP_GREATER_THAN_OR_EQUAL expression
                     | expression OP_LESS_THAN expression
                     | expression OP_LESS_THAN_OR_EQUAL
                     | expression OP_LOGICAL_AND expression
                     | expression OP_INEQUALITY expression
                     | expression OP_EQUALITY expression
                     | expression OP_LOGICAL_OR expression
                     | expression OP_ADD expression
                     | expression OP_SUBTRACT expression
                     | expression OP_MULTIPLY expression
                     | expression OP_DIVIDE expression
                     | expression OP_BITWISE_OR expression
                     | expression OP_BITWISE_XOR expression
                     | expression OP_BITWISE_AND expression
                     | expression OP_BITWISE_LEFT expression
                     | expression OP_BITWISE_RIGHT expression
                     | expression OP_MODULUS expression
                     | OP_SUBTRACT expression
                     | OP_BITWISE_NOT expression
                     | OP_NOT expression
                     | OP_INCREMENT field_access
                     | field_access OP_INCREMENT
                     | OP_DECREMENT field_access
                     | field_access OP_DECREMENT
                     | '[' LITERAL_FLOAT ',' LITERAL_FLOAT ',' LITERAL_FLOAT ']'
                     | field_access                                                 
                     ;

constant_expression  : LITERAL_INT                                                  { $$.node = new IntLiteralExpression($1.numberi); }
                     | LITERAL_INT_HEX
                     | LITERAL_FLOAT
                     | LITERAL_STRING
                     | VALUE_OBJECT_SELF
                     | VALUE_OBJECT_INVALID
                     | VALUE_TRUE
                     | VALUE_FALSE
                     ;

data_type            : TYPE_INT                                              { ; }
                     | TYPE_FLOAT                                            { ; }
                     | TYPE_OBJECT                                           { ; }
                     | TYPE_VOID                                             { ; }
                     | TYPE_EVENT                                            { ; }
                     | TYPE_EFFECT                                           { ; }
                     | TYPE_ITEM_PROPERTY                                    { ; }
                     | TYPE_LOCATION                                         { ; }
                     | TYPE_STRING                                           { ; }
                     | TYPE_TALENT                                           { ; }
                     | TYPE_VECTOR                                           { ; }
                     | TYPE_ACTION                                           { ; }
                     | TYPE_STRUCT IDENTIFIER                                { ; }
                     ;

field_access         : IDENTIFIER                                               { $$.node = new FieldAccess($1.text); }
                     | IDENTIFIER '.' IDENTIFIER                                { $$.node = new FieldAccess($1.text, $3.text); }
                     | field_access '.' IDENTIFIER                              { $$.node = new FieldAccess((FieldAccess)$1.node, $3.text); }
                     ;

%%
