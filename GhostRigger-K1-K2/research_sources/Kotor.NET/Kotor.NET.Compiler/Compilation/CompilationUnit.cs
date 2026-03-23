using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Scripting.Calculator;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation
{
    public class CompilationUnit : ASTNode
    {
        public List<ASTNode> Declarations { get; set; }

        public CompilationUnit(List<ASTNode> declarations)
        {
            Declarations = declarations;
        }

        public CompilationUnit(ASTNode declaration)
        {
            Declarations = new List<ASTNode> { declaration };
        }

        public CompilationUnit()
        {
            Declarations = new();
        }

        public void Compile(SymbolTable symbolTable, NCS ncs) => throw new NotImplementedException();
    }
}
