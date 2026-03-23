using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorNCS;

namespace Kotor.NET.Scripting.Compilation.Expression.Constant
{
    public class FloatConstantExpression : IExpression
    {
        public float Value { get; set; }

        public FloatConstantExpression(float value)
        {
            Value = value;
        }

        public DataType GetDataType()
        {
            return DataType.Float;
        }

        public void Compile(SymbolTable symbolTable, NCS ncs)
        {
            ncs.Add(new NCSInstruction.CONSTF(Value));
        }
    }
}
