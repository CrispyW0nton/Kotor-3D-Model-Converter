using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation
{
    public class IntLiteralExpression : IExpression
    {
        public int Value { get; set; }

        public IntLiteralExpression(int value)
        {
            Value = value;
        }

        public DataType GetDataType() => DataType.Int;
        public void Compile(SymbolTable symbolTable, NCS ncs) => throw new NotImplementedException();

        public override string ToString() => $"{Value}";
    }
}
