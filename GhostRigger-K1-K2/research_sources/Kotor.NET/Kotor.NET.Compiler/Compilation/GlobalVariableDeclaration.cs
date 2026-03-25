using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Scripting.Calculator;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation
{
    public class GlobalVariableDeclaration : ASTNode
    {
        public DataType DataType { get; }
        public string Identifier { get; }

        public GlobalVariableDeclaration(DataType dataType, string identifier)
        {
            DataType = dataType;
            Identifier = identifier;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            symbolTable.DeclareGlobalVariable(Identifier, DataType);
        }

        public override string ToString()
        {
            return $"{DataType.Type} {Identifier};";
        }
    }
}
