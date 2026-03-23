using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Constant
{
    public class IntConstantExpression : IExpression
    {
        public int Value { get; set; }

        public IntConstantExpression(int value)
        {
            Value = value;
        }

        public DataType GetDataType()
        {
            return DataType.Int;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            ncs.Add(new NCSInstruction.CONSTI(Value));
        }
    }
}
