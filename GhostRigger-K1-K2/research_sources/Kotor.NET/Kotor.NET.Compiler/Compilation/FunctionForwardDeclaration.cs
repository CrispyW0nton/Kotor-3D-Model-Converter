using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Scripting.Calculator;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation
{
    public class FunctionForwardDeclaration : ASTNode
    {
        public DataType ReturnType { get; }
        public string Symbol { get; }
        public List<FunctionParameter> Parameters { get; }

        public FunctionForwardDeclaration(DataType returnType, string symbol, List<FunctionParameter> parameters)
        {
            ReturnType = returnType;
            Symbol = symbol;
            Parameters = parameters;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs) => throw new NotImplementedException();
    }
}
